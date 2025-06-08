import unittest
from datetime import date, timedelta

from intervention_planner import ScholarRecord, compute_priority, build_escalation_list


class TestEscalationList(unittest.TestCase):
    def test_filters_high_risk_overdue_and_score(self):
        today = date(2024, 4, 1)
        records = [
            ScholarRecord(
                scholar_id="s-1",
                name="Avery",
                cohort="2024",
                owner="Casey",
                channel_preference="email",
                last_touch=today - timedelta(days=40),
                risk_score=92,
                flags=["housing"],
            ),
            ScholarRecord(
                scholar_id="s-2",
                name="Blake",
                cohort="2024",
                owner="Casey",
                channel_preference="sms",
                last_touch=today - timedelta(days=2),
                risk_score=95,
                flags=[],
            ),
            ScholarRecord(
                scholar_id="s-3",
                name="Carmen",
                cohort="2023",
                owner="Dee",
                channel_preference="call",
                last_touch=today - timedelta(days=50),
                risk_score=55,
                flags=[],
            ),
        ]
        scored = [
            compute_priority(record, today, high=70, medium=40, soon_days=14, stale_days=60, stale_boost=15)
            for record in records
        ]
        escalations = build_escalation_list(scored, limit=5, min_score=100)

        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations[0]["name"], "Avery")
        self.assertEqual(escalations[0]["status"], "overdue")


if __name__ == "__main__":
    unittest.main()
