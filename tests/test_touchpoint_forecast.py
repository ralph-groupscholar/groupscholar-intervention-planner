import unittest
from datetime import date

import intervention_planner as planner


class TouchpointForecastTest(unittest.TestCase):
    def make_record(self, due_in_days):
        return planner.ScoredRecord(
            scholar_id="s-1",
            name="Test Scholar",
            cohort="Test",
            owner="Owner",
            channel_preference="email",
            last_touch=None,
            risk_score=50.0,
            flags=[],
            cadence_days=21,
            due_date=None,
            days_since_touch=None,
            due_in_days=due_in_days,
            overdue_days=None,
            status="on-track",
            priority_score=50.0,
            recommended_action="Check in",
            priority_reasons=[],
            stale_touch=False,
            stale_days=None,
        )

    def test_forecast_includes_overdue(self):
        today = date(2025, 1, 15)
        records = [
            self.make_record(-2),
            self.make_record(0),
            self.make_record(1),
            self.make_record(4),
            self.make_record(10),
            self.make_record(None),
        ]
        forecast = planner.summarize_touchpoint_forecast(records, today, window_days=7, include_overdue=True)
        self.assertEqual(forecast["overdue"], 1)
        self.assertEqual(forecast["no_due_date"], 1)
        self.assertEqual(forecast["beyond_window"], 1)
        self.assertEqual(forecast["daily"][0]["count"], 2)
        self.assertEqual(forecast["daily"][1]["count"], 1)
        self.assertEqual(forecast["daily"][4]["count"], 1)

    def test_forecast_excludes_overdue(self):
        today = date(2025, 1, 15)
        records = [
            self.make_record(-1),
            self.make_record(0),
            self.make_record(3),
        ]
        forecast = planner.summarize_touchpoint_forecast(records, today, window_days=5, include_overdue=False)
        self.assertEqual(forecast["overdue"], 1)
        self.assertEqual(forecast["daily"][0]["count"], 1)
        self.assertEqual(forecast["daily"][3]["count"], 1)


if __name__ == "__main__":
    unittest.main()
