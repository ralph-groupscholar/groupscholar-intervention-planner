import unittest

import intervention_planner as planner


class TouchpointHorizonTest(unittest.TestCase):
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

    def test_horizon_buckets(self):
        records = [
            self.make_record(-3),
            self.make_record(0),
            self.make_record(5),
            self.make_record(8),
            self.make_record(14),
            self.make_record(20),
            self.make_record(31),
            self.make_record(None),
        ]
        horizon = planner.summarize_touchpoint_horizon(records)
        self.assertEqual(horizon["overdue"], 1)
        self.assertEqual(horizon["next_7_days"], 2)
        self.assertEqual(horizon["next_14_days"], 2)
        self.assertEqual(horizon["next_30_days"], 1)
        self.assertEqual(horizon["later"], 1)
        self.assertEqual(horizon["no_due_date"], 1)


if __name__ == "__main__":
    unittest.main()
