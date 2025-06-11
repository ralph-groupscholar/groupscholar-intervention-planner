import unittest

import intervention_planner as planner


class CadenceAdherenceTest(unittest.TestCase):
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

    def test_cadence_adherence_summary(self):
        records = [
            self.make_record(7, "on-track"),
            self.make_record(7, "overdue"),
            self.make_record(21, "due-soon"),
            self.make_record(45, "no-touch"),
        ]
        summary = planner.summarize_cadence_adherence(records)
        self.assertEqual(summary["overall"]["total"], 4)
        self.assertEqual(summary["overall"]["compliant"], 2)
        self.assertEqual(summary["overall"]["overdue"], 1)
        self.assertEqual(summary["overall"]["no_touch"], 1)
        self.assertEqual(summary["overall"]["compliance_rate"], 0.5)

        self.assertEqual(summary["high"]["total"], 2)
        self.assertEqual(summary["high"]["compliant"], 1)
        self.assertEqual(summary["high"]["overdue"], 1)
        self.assertEqual(summary["high"]["compliance_rate"], 0.5)

        self.assertEqual(summary["medium"]["total"], 1)
        self.assertEqual(summary["medium"]["compliant"], 1)
        self.assertEqual(summary["medium"]["compliance_rate"], 1.0)

        self.assertEqual(summary["low"]["total"], 1)
        self.assertEqual(summary["low"]["no_touch"], 1)
        self.assertEqual(summary["low"]["compliance_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
