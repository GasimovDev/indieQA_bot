"""Regression tests for telemetry detection and portable report exports."""
import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from analysis.bug_detector import BugDetector
from analysis.reporter import BugReporter

ROOT = Path(__file__).resolve().parents[1]


def frames(count: int, **overrides: object) -> pd.DataFrame:
    rows = []
    for i in range(count):
        row = dict(frame_id=i, timestamp=i / 60, pos_x=100., pos_y=100.,
                   vel_x=0., vel_y=0., is_grounded=True,
                   active_input="none", collision_state=True)
        row.update(overrides)
        rows.append(row)
    return pd.DataFrame(rows)


class DetectorTests(unittest.TestCase):
    def test_oob_does_not_mask_fall_and_events_are_debounced(self) -> None:
        data = frames(400, pos_x=900., vel_y=2., is_grounded="False", collision_state="False")
        data.pos_y = 700 + data.frame_id * 2
        bugs = BugDetector().process_telemetry(data)
        self.assertEqual([b["type"] for b in bugs], ["Out of Bounds", "Infinite Fall"])
        self.assertEqual(bugs[1]["frame_id"], 120)
        self.assertEqual(len(bugs[1]["reproduction_sequence"]), 30)

    def test_normal_motion_and_idle_are_not_bugs(self) -> None:
        data = frames(600)
        self.assertEqual(BugDetector().process_telemetry(data), [])

    def test_returning_patrol_is_not_a_softlock(self) -> None:
        data = frames(900, active_input="right")
        data.pos_x = [100. + min(i % 300, 300 - i % 300) for i in range(900)]
        self.assertEqual(BugDetector().process_telemetry(data), [])

    def test_jump_spam_in_pit_reports_once_then_rearms_after_exit(self) -> None:
        data = frames(700, pos_x=444., pos_y=558., active_input="right+jump")
        # Periodic jumps in the pit; individual endpoints need not match.
        for i in range(len(data)):
            phase = i % 41
            data.loc[i, "pos_y"] = 558. - (10.25 * phase - .25 * phase * (phase + 1))
            data.loc[i, "is_grounded"] = phase == 0
        detector = BugDetector()
        bugs = detector.process_telemetry(data)
        self.assertEqual([b["type"] for b in bugs], ["Softlock"])
        self.assertGreater(bugs[0]["frame_id"], 300)
        second = frames(1, pos_x=340., pos_y=404., collision_state=False)
        second.frame_id += 700
        detector.process_telemetry(second)
        data.frame_id += 701
        bugs = detector.process_telemetry(data)
        self.assertEqual(sum(b["type"] == "Softlock" for b in bugs), 2)

    def test_wall_clip_requires_collision(self) -> None:
        data = frames(3)
        data.loc[1:, "pos_x"] = 148.
        bugs = BugDetector().process_telemetry(data)
        self.assertEqual([b["type"] for b in bugs], ["Wall Clip"])
        data.collision_state = False
        self.assertEqual(BugDetector().process_telemetry(data), [])

    def test_respawn_does_not_report_wall_clip(self) -> None:
        data = frames(2, collision_state=False, is_grounded=False)
        data.loc[0, "pos_y"] = 10000.
        data.loc[1, "pos_y"] = 404.5
        data.loc[1, "vel_y"] = .5
        self.assertNotIn("Wall Clip", [b["type"] for b in BugDetector().process_telemetry(data)])

    def test_missing_columns_and_nan_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BugDetector().process_telemetry(pd.DataFrame())
        data = frames(2)
        data.loc[0, "pos_x"] = float("nan")
        with self.assertRaises(ValueError):
            BugDetector().process_telemetry(data)

    def test_batch_boundary_preserves_fall_evidence(self) -> None:
        data = frames(200, vel_y=2., collision_state=False, is_grounded=False)
        data.pos_y = data.frame_id * 2
        detector = BugDetector()
        detector.process_telemetry(data.iloc[:100])
        bugs = detector.process_telemetry(data.iloc[100:])
        self.assertEqual([b["type"] for b in bugs], ["Infinite Fall"])

    def test_report_json_and_markdown(self) -> None:
        bug = BugDetector().process_telemetry(frames(1, pos_x=-1.))[0]
        with tempfile.TemporaryDirectory(dir=ROOT / 'data') as directory:
            BugReporter(directory).generate_all_reports([bug])
            output = Path(directory)
            self.assertEqual(json.loads(next(output.glob('*.json')).read_text()), bug)
            self.assertIn('Reproduction', next(output.glob('*.md')).read_text())


if __name__ == '__main__':
    unittest.main()
