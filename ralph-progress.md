# Ralph Progress Log

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
