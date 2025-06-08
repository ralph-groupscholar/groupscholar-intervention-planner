import unittest

import intervention_planner as planner


class OwnerHorizonTest(unittest.TestCase):
    def make_record(self, owner, due_in_days, priority):
        return planner.ScoredRecord(
            scholar_id="s-1",
            name="Test Scholar",
            cohort="Test",
            owner=owner,
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
            priority_score=priority,
            recommended_action="Check in",
            priority_reasons=[],
            stale_touch=False,
            stale_days=None,
        )

    def test_owner_horizon_buckets(self):
        records = [
            self.make_record("Advisor A", -2, 80.0),
            self.make_record("Advisor A", 3, 60.0),
            self.make_record("Advisor A", None, 40.0),
            self.make_record("Advisor B", 10, 50.0),
            self.make_record("Advisor B", 25, 70.0),
            self.make_record("Advisor B", 40, 90.0),
        ]
        horizon = planner.summarize_owner_horizon(records)
        self.assertEqual(horizon[0]["owner"], "Advisor A")
        advisor_a = horizon[0]
        self.assertEqual(advisor_a["total"], 3)
        self.assertEqual(advisor_a["overdue"], 1)
        self.assertEqual(advisor_a["next_7_days"], 1)
        self.assertEqual(advisor_a["next_14_days"], 0)
        self.assertEqual(advisor_a["next_30_days"], 0)
        self.assertEqual(advisor_a["later"], 0)
        self.assertEqual(advisor_a["no_due_date"], 1)
        self.assertEqual(advisor_a["avg_priority"], 60.0)

        advisor_b = horizon[1]
        self.assertEqual(advisor_b["owner"], "Advisor B")
        self.assertEqual(advisor_b["total"], 3)
        self.assertEqual(advisor_b["overdue"], 0)
        self.assertEqual(advisor_b["next_7_days"], 0)
        self.assertEqual(advisor_b["next_14_days"], 1)
        self.assertEqual(advisor_b["next_30_days"], 1)
        self.assertEqual(advisor_b["later"], 1)
        self.assertEqual(advisor_b["no_due_date"], 0)
        self.assertEqual(advisor_b["avg_priority"], 70.0)


if __name__ == "__main__":
    unittest.main()
