"""Dashboard lifecycle and interaction checks, including growing/replaced logs."""
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from analysis.bug_detector import BugDetector
from dashboard.live import LiveRun, read_telemetry, prioritize
from dashboard.advisor import LocalFixAdvisor

ROOT = Path(__file__).resolve().parents[1]


def falling(count: int, start: float = 1000.) -> pd.DataFrame:
    return pd.DataFrame([dict(frame_id=i, timestamp=start+i/60, pos_x=260., pos_y=700.+i*2,
                              vel_x=0., vel_y=2., is_grounded=False, collision_state=False,
                              active_input='right') for i in range(count)])


class LiveDataTests(unittest.TestCase):
    def test_local_advisor_is_api_ready_and_contextual(self) -> None:
        bug = {'type': 'Wall Clip', 'severity': 'CRITICAL', 'priority': 'P0',
               'frame_id': 85, 'coordinates_xyz': [800., 389., 0.],
               'reproduction_sequence': ['right', 'right+jump']}
        advisor = LocalFixAdvisor()
        self.assertIn('right-wall seam', advisor.answer('recommend a fix', bug))
        self.assertIn('right+jump', advisor.answer('How do I reproduce it?', bug))
        self.assertIn('P0', advisor.answer('why is this urgent?', bug))

    def test_incremental_matches_batch_and_does_not_duplicate(self) -> None:
        data = falling(350)
        run = LiveRun()
        for stop in [30, 120, 121, 220, 350, 350]:
            bugs = run.update(data.iloc[:stop])
        expected = BugDetector().process_telemetry(data)
        self.assertEqual([(b['type'], b['frame_id']) for b in bugs], [(b['type'], b['frame_id']) for b in expected])

    def test_new_run_same_or_greater_length_resets(self) -> None:
        run = LiveRun()
        run.update(falling(150))
        run.update(falling(150, 2000.))
        self.assertEqual(run.generation, 1)
        run.update(falling(180, 3000.))
        self.assertEqual(run.generation, 2)
        self.assertEqual(len(run.detector.detected_bugs), 2)
        self.assertTrue(all(b['timestamp'] >= 3000 for b in run.detector.detected_bugs))

    def test_truncation_and_empty_run_reset(self) -> None:
        run = LiveRun()
        run.update(falling(200))
        self.assertEqual(len(run.update(falling(50))), 1)
        self.assertEqual(run.update(pd.DataFrame()), [])
        self.assertEqual(run.rows_seen, 0)

    def test_partial_csv_line_waits_until_complete(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / 'data') as directory:
            path = Path(directory) / 'telemetry.csv'
            raw = falling(3).to_csv(index=False).encode()
            path.write_bytes(raw[:-5])
            self.assertEqual(len(read_telemetry(path)), 2)
            path.write_bytes(raw)
            self.assertEqual(len(read_telemetry(path)), 3)

    def test_priorities_preserve_severity(self) -> None:
        bugs = BugDetector().process_telemetry(falling(150))
        result = prioritize(bugs)
        self.assertEqual([b['priority'] for b in result], ['P0', 'P1'])
        self.assertTrue(all('priority' not in b for b in bugs))
        self.assertEqual(result[1]['severity'], 'HIGH')


@unittest.skipIf(sys.version_info >= (3, 14), 'Streamlit AppTest hangs on Python 3.14; review the running browser instead.')
class DashboardTests(unittest.TestCase):
    def test_filters_evidence_and_live_toggle(self) -> None:
        app = AppTest.from_file(str(ROOT / 'dashboard/app.py')).run(timeout=40)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(app.metric[1].value, f"{len(read_telemetry(ROOT / 'data/logs/telemetry.csv')):,}")
        app.selectbox(key='severity').select('HIGH').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue((app.dataframe[-1].value.severity == 'HIGH').all())
        app.selectbox(key='kind').select('Wall Clip').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.dataframe[-1].value.empty)
        app.selectbox(key='severity').select('ALL').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue((app.dataframe[-1].value.type == 'Wall Clip').all())
        app.toggle(key='live').set_value(False).run(timeout=30)
        self.assertEqual(len(app.exception), 0)

    def test_no_data_is_friendly(self) -> None:
        with patch('dashboard.live.read_telemetry', return_value=pd.DataFrame()):
            app = AppTest.from_file(str(ROOT / 'dashboard/app.py')).run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertIn('Ready to explore', app.info[0].value)


if __name__ == '__main__':
    unittest.main()
