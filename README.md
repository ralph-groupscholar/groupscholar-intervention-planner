# Group Scholar Intervention Planner

Group Scholar Intervention Planner is a local-first CLI that turns scholar risk signals and last-touch dates into a prioritized action queue. It helps program teams focus on the most urgent outreach, keep cadence consistent by risk tier, and generate a shareable JSON report for weekly ops reviews.

## Features
- Prioritized action queue based on risk score, cadence, and urgency.
- Overdue/due-soon/on-track touchpoint classification.
- Tiered cadence guidance (high/medium/low risk).
- JSON export for downstream dashboards or briefings.
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
  --soon-days 10 \
  --json report.json
```

### Options
- `--input` (required): path to the intake CSV.
- `--limit`: number of priority actions to print (default: 10).
- `--high-risk`: risk score threshold for high risk (default: 70).
- `--medium-risk`: risk score threshold for medium risk (default: 40).
- `--soon-days`: days ahead to flag a due-soon touch (default: 14).
- `--today`: override today's date in `YYYY-MM-DD` format.
- `--json`: write a JSON report to the given path.

## CSV Schema
Required headers (case-insensitive):
- `id` or `scholar_id`
- `name`
- `cohort`
- `channel_preference` (or `preferred_channel`)
- `last_touch` (or `last_contact`) in `YYYY-MM-DD`
- `risk_score`
- `flags` (semicolon-separated)

## Output
The CLI prints:
- A summary of touchpoint status and risk tiers.
- A priority action queue with recommended next steps.
- Cadence guidance for each tier.

## Tech
- Python 3 (standard library only)

## Notes
This tool is designed for local-first workflows and can be run on any machine with Python 3.
