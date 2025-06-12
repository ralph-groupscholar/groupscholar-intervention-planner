import unittest

import intervention_planner as planner


class StatusByRiskTest(unittest.TestCase):
    def make_record(self, cadence_days, status):
        return planner.ScoredRecord(
            scholar_id="s-1",
            name="Test Scholar",
            cohort="Test",
            owner="Owner",
            channel_preference="email",
            last_touch=None,
            risk_score=50.0,
            flags=[],
            cadence_days=cadence_days,
            due_date=None,
            days_since_touch=None,
            due_in_days=None,
            overdue_days=None,
            status=status,
            priority_score=50.0,
            recommended_action="Check in",
            priority_reasons=[],
            stale_touch=False,
            stale_days=None,
        )

    def test_status_by_risk(self):
        records = [
            self.make_record(7, "overdue"),
            self.make_record(7, "due-soon"),
            self.make_record(21, "on-track"),
            self.make_record(21, "no-touch"),
            self.make_record(45, "overdue"),
        ]
        summary = planner.summarize_status_by_risk(records)
        self.assertEqual(summary["high"]["overdue"], 1)
        self.assertEqual(summary["high"]["due_soon"], 1)
        self.assertEqual(summary["high"]["on_track"], 0)
        self.assertEqual(summary["high"]["no_touch"], 0)
        self.assertEqual(summary["medium"]["on_track"], 1)
        self.assertEqual(summary["medium"]["no_touch"], 1)
        self.assertEqual(summary["low"]["overdue"], 1)


if __name__ == "__main__":
    unittest.main()
