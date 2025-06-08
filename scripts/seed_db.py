#!/usr/bin/env python3
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import intervention_planner as planner  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the Intervention Planner tables with sample data.")
    parser.add_argument("--input", default="data/sample.csv", help="CSV path for seed run")
    parser.add_argument("--schema", default=planner.DEFAULT_DB_SCHEMA, help="Postgres schema name")
    parser.add_argument("--run-label", help="Label for the seeded run")
    parser.add_argument("--today", help="Override today's date for the seed run (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = date.today()
    if args.today:
        parsed = planner.parse_date(args.today)
        if not parsed:
            raise SystemExit("Invalid --today date format. Use YYYY-MM-DD.")
        today = parsed

    schema = planner.validate_schema_name(args.schema)
    run_label = args.run_label or planner.default_run_label(args.input, today)
    records = planner.load_csv(args.input)
    scored = planner.build_report(records, today, high=70, medium=40, soon_days=14, stale_days=60, stale_boost=15)
    owners = planner.summarize_owners(scored)
    owner_horizon = planner.summarize_owner_horizon(scored)
    owner_alerts = planner.build_owner_alerts(
        owners,
        overdue_threshold=2,
        no_touch_threshold=1,
        total_threshold=8,
    )
    summary = planner.summarize(scored)
    summary["owner_alerts"] = owner_alerts
    touchpoint_forecast = planner.summarize_touchpoint_forecast(
        scored,
        today,
        window_days=21,
        include_overdue=True,
    )
    escalation_candidates = planner.build_escalation_list(scored, limit=5, min_score=90)
    payload = {
        "generated_at": planner.datetime.now().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "summary": summary,
        "channel_mix": planner.summarize_channels(scored),
        "high_impact_flags": planner.summarize_flags(scored),
        "cohort_summary": planner.summarize_cohorts(scored),
        "owner_summary": owners,
        "owner_horizon": owner_horizon,
        "owner_queue": planner.build_owner_queue(scored, limit=5, size=3),
        "touchpoint_forecast": touchpoint_forecast,
        "channel_batches": planner.build_channel_batches(scored, limit=4, size=3),
        "escalation_candidates": escalation_candidates,
        "records": [planner.asdict(record) for record in scored],
    }

    dsn = planner.resolve_db_dsn()
    if not dsn:
        raise SystemExit("Database env vars missing. Set GS_DB_DSN or GS_DB_HOST/GS_DB_NAME/GS_DB_USER/GS_DB_PASSWORD.")

    planner.write_run_to_db(
        dsn=dsn,
        schema=schema,
        run_label=run_label,
        args=argparse.Namespace(
            input=args.input,
            high_risk=70,
            medium_risk=40,
            soon_days=14,
            limit=10,
            cohort_limit=5,
            owner_limit=5,
            owner_queue_limit=5,
            owner_queue_size=3,
            channel_batch_limit=4,
            channel_batch_size=3,
        ),
        payload=payload,
    )
    print(f"Seeded sample data into schema '{schema}'.")


if __name__ == "__main__":
    main()
