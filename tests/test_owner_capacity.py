import unittest

import intervention_planner as planner


class OwnerCapacityTest(unittest.TestCase):
    def make_record(self, owner, due_in_days):
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
            priority_score=60.0,
            recommended_action="Check in",
            priority_reasons=[],
            stale_touch=False,
            stale_days=None,
        )

    def test_owner_capacity_gap_and_utilization(self):
        records = [
            self.make_record("Advisor A", -2),
            self.make_record("Advisor A", 3),
            self.make_record("Advisor A", None),
            self.make_record("Advisor B", 1),
            self.make_record("Advisor B", 5),
            self.make_record("Advisor B", 9),
        ]
        records.extend([self.make_record("Advisor C", -1) for _ in range(15)])

        capacity = planner.summarize_owner_capacity(records, window_days=7, daily_capacity=2, include_overdue=True)
        self.assertEqual(capacity[0]["owner"], "Advisor C")
        advisor_c = capacity[0]
        self.assertEqual(advisor_c["due_within_window"], 15)
        self.assertEqual(advisor_c["overdue"], 15)
        self.assertEqual(advisor_c["capacity"], 14)
        self.assertEqual(advisor_c["gap"], 1)
        self.assertEqual(advisor_c["utilization"], 1.07)

        advisor_a = next(item for item in capacity if item["owner"] == "Advisor A")
        self.assertEqual(advisor_a["due_within_window"], 2)
        self.assertEqual(advisor_a["overdue"], 1)
        self.assertEqual(advisor_a["capacity"], 14)
        self.assertEqual(advisor_a["gap"], 0)
        self.assertEqual(advisor_a["utilization"], 0.14)


if __name__ == "__main__":
    unittest.main()
