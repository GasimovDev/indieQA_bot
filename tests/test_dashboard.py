"""Streamlit interaction smoke test against the latest simulation output."""
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_latest_run_filters_and_views(self) -> None:
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard/app.py'))
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        if app.selectbox:
            app.selectbox[0].select('HIGH').run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue((app.dataframe[0].value.severity == 'HIGH').all())
            app.selectbox[0].select('MEDIUM').run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(app.dataframe[0].value.empty)
        app.radio[0].set_value('Full trajectory').run()
        self.assertEqual(len(app.exception), 0)


if __name__ == '__main__':
    unittest.main()
