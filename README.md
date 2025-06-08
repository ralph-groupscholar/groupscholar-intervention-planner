# Group Scholar Intervention Planner

Group Scholar Intervention Planner is a local-first CLI that turns scholar risk signals and last-touch dates into a prioritized action queue. It helps program teams focus on the most urgent outreach, keep cadence consistent by risk tier, and generate a shareable JSON report for weekly ops reviews.

## Features
- Prioritized action queue based on risk score, cadence, and urgency.
- Overdue/due-soon/on-track touchpoint classification.
- Tiered cadence guidance (high/medium/low risk).
- Stale touch detection with configurable aging boost.
- Channel mix, high-impact flag counts, and cohort hotspot summary.
- Touchpoint horizon buckets to plan near-term outreach coverage.
- Touchpoint forecast to estimate daily outreach load for upcoming windows.
- Owner load summary to balance outreach workload.
- Owner touchpoint horizon to visualize upcoming workload by advisor.
- Channel batch plan to coordinate outreach by preferred channel.
- Escalation candidate list for high-risk overdue or no-touch cases.
- JSON export for downstream dashboards or briefings.
- Optional Postgres persistence for run history and records.
- Sample dataset to test the workflow quickly.

## Quickstart

```bash
python3 intervention_planner.py --input data/sample.csv
```

## Usage

```bash
python3 intervention_planner.py \
  --input data/sample.csv \
  --limit 5 \
  --cohort-limit 3 \
  --owner-limit 5 \
  --owner-queue-limit 4 \
  --owner-queue-size 2 \
  --channel-batch-limit 3 \
  --channel-batch-size 2 \
  --escalation-limit 4 \
  --escalation-min-score 95 \
  --soon-days 10 \
  --json report.json
```

### Options
- `--input` (required): path to the intake CSV.
- `--limit`: number of priority actions to print (default: 10).
- `--high-risk`: risk score threshold for high risk (default: 70).
- `--medium-risk`: risk score threshold for medium risk (default: 40).
- `--soon-days`: days ahead to flag a due-soon touch (default: 14).
- `--stale-days`: days since last touch to mark as stale (default: 60).
- `--stale-boost`: priority boost for stale-touch records (default: 15).
- `--cohort-limit`: number of cohorts to list in the hotspot summary (default: 5).
- `--owner-limit`: number of owners to list in the load summary (default: 5).
- `--owner-queue-limit`: number of owners to show in the action queue (default: 5).
- `--owner-queue-size`: number of actions to show per owner (default: 3).
- `--owner-overdue-threshold`: overdue count to flag an owner in alerts (default: 2).
- `--owner-no-touch-threshold`: no-touch count to flag an owner in alerts (default: 1).
- `--owner-total-threshold`: total scholar count to flag an owner in alerts (default: 8).
- `--channel-batch-limit`: number of channels to show in the batch plan (default: 4).
- `--channel-batch-size`: number of actions to show per channel batch (default: 3).
- `--escalation-limit`: number of escalation candidates to show (default: 5).
- `--escalation-min-score`: minimum priority score for escalation candidates (default: 90).
- `--forecast-window-days`: days ahead to include in the touchpoint forecast (default: 21).
- `--forecast-include-overdue`: include overdue touches in the forecast day 0 count.
- `--today`: override today's date in `YYYY-MM-DD` format.
- `--json`: write a JSON report to the given path.
- `--explain`: include priority reasons in the action queue output.
- `--db-write`: write the run + records to Postgres (requires `psycopg`).
- `--db-schema`: Postgres schema to store tables (letters/numbers/underscores only).
- `--run-label`: optional label to tag the database run (defaults to `<input-stem>-<YYYY-MM-DD>`).

## CSV Schema
Required headers (case-insensitive):
- `id` or `scholar_id`
- `name`
- `cohort`
- `owner` (or `advisor`, `case_manager`, `coach`)
- `channel_preference` (or `preferred_channel`)
- `last_touch` (or `last_contact`) in `YYYY-MM-DD`
- `risk_score`
- `flags` (semicolon-separated)

## Output
The CLI prints:
- A summary of touchpoint status and risk tiers.
- Overdue aging buckets and no-touch counts by risk tier.
- Touchpoint horizon buckets for upcoming outreach windows.
- Touchpoint forecast with daily counts for the selected window.
- Stale-touch counts by risk tier.
- Channel mix and high-impact flag highlights.
- Cohort hotspot summary to target outreach coverage.
- Owner load summary to balance staff coverage.
- Owner touchpoint horizon to forecast upcoming advisor workload.
- Owner alerts to flag overloaded caseloads or missing-touch hotspots.
- Owner action queues to ensure each advisor has clear next steps.
- Channel batch plan to coordinate outreach across preferred channels.
- Escalation candidates list for urgent high-risk outreach.
- A priority action queue with recommended next steps.
- Cadence guidance for each tier.
When using `--explain`, each action includes the priority drivers (risk tier, due status, high-impact flags).

## Tech
- Python 3
- Postgres (optional) via `psycopg`

## Tests

```bash
python3 -m unittest discover -s tests
```

## Postgres Integration (Optional)

Install the dependency:

```bash
pip install psycopg[binary]
```

Set environment variables (do not hardcode credentials):

```bash
export GS_DB_HOST=your_host
export GS_DB_PORT=5432
export GS_DB_NAME=your_db
export GS_DB_USER=your_user
export GS_DB_PASSWORD=your_password
# Optional if your server does not require SSL:
export GS_DB_SSLMODE=disable
```

You can also provide a full `GS_DB_DSN` (or `DATABASE_URL`) instead of the individual env vars.

Then run:

```bash
python3 intervention_planner.py --input data/sample.csv --db-write --run-label "Weekly outreach"
```

Database runs capture owner alerts and per-scholar priority reasons for downstream reporting.

Seed sample data (creates tables if missing):

```bash
python3 scripts/seed_db.py
```

## Notes
This tool is designed for local-first workflows and can be run on any machine with Python 3.
