# Ralph Progress Log

## Iteration 22
- Added status-by-risk tier breakdown to highlight overdue/due-soon/on-track/no-touch mix per tier.
- Printed the new risk-tier status table in CLI output and embedded it in JSON/DB summaries.
- Fixed Postgres insert placeholder counts and reseeded the production schema.

## Iteration 20
- Added owner capacity planning to size near-term workload vs. daily outreach capacity.
- Persisted owner capacity data in JSON/DB payloads and wired CLI output/reporting.
- Added unit coverage and updated seed payload + README options for capacity planning.

## Iteration 18
- Added owner touchpoint horizon summary to forecast upcoming advisor workloads.
- Included owner horizon data in CLI output, JSON payloads, and database runs.
- Added unit coverage for the owner horizon bucket logic and updated seed workflow.

## Iteration 91
- Added owner alert watchlists with overdue/no-touch/total thresholds to surface overloaded caseloads.
- Wired owner alerts into CLI output and the JSON/DB summary payloads for reporting.
- Updated README and seed workflow defaults for the new alert thresholds.

## Iteration 43
- Seeded the production Postgres schema with sample intervention planner data.
- Documented the DSN-based database option in the README.

## Iteration 43
- Started Group Scholar Intervention Planner, a local-first CLI that prioritizes scholar touchpoints based on risk, cadence, and urgency.
- Implemented CSV parsing, scoring logic, summary reporting, and JSON export.
- Added a sample dataset and documented usage in the README.

## Iteration 53
- Added channel mix, high-impact flag counts, and cohort hotspot summaries to surface outreach coverage gaps.
- Introduced a cohort summary limit flag and extended JSON output with the new aggregates.
- Updated README with the new reporting features and option.

## Iteration 53 (cont.)
- Added schema validation and default run labels for Postgres writes.
- Updated the seed script to reuse the new validation + labeling helpers.
- Reseeded the production database schema with the latest sample run.

## Iteration 80
- Added priority-reason tracking for each action so teams can explain why a scholar is ranked higher.
- Introduced a `--explain` flag to show those reasons in the action queue output.
- Updated README options/output notes for the new explain mode.

## Iteration 33
- Added optional Postgres persistence with schema-managed run + record tables and a CLI flag to store runs.
- Created a seed script to populate production tables with sample data and documented the database workflow.
- Expanded README with Postgres setup, env vars, and seeding instructions.

## Iteration 81
- Added channel batch planning to group outreach actions by preferred channel with prioritized examples.
- Persisted channel batch configuration/output in the JSON payload and Postgres runs schema.
- Updated seed script and README with the new batch options and output notes.

## Iteration 92
- Added touchpoint horizon buckets to summarize upcoming outreach windows.
- Printed the new horizon summary in CLI output and included it in JSON/DB summary payloads.
- Added unit coverage for the horizon bucketing logic and documented the test command.

## Iteration 17
- Added Postgres persistence for owner alerts and per-scholar priority reasons in run records.
- Extended schema migrations to backfill new alert/reason columns with safe defaults.
- Documented the new database payload coverage in the README.

## Iteration 93
- Added touchpoint forecast reporting with daily outreach counts and optional overdue inclusion.
- Persisted touchpoint forecast data in JSON output and Postgres runs schema.
- Added seed payload updates plus unit coverage for the forecast behavior.
