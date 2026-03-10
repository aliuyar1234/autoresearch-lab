# Phase 6 — Reports, night runs, and campaign UX

Status: complete

## Objective

Make the lab pleasant and useful for actual overnight work by adding `night`, daily reports, leaderboards, and champion cards.

## Deliverables

1. unattended `night` session orchestration
2. report generation
3. campaign-local leaderboard views
4. champion cards and archive summaries
5. crash summaries
6. smoke-tested overnight mini-session

## Exact files to create

Required new files:
- `lab/reports/__init__.py`
- `lab/reports/daily.py`
- `lab/reports/leaderboard.py`
- `lab/reports/champion.py`
- `lab/reports/crashes.py`
- `lab/reports/render.py`
- `tests/integration/test_report_generation.py`
- `tests/integration/test_night_session_fake.py`

Required file updates:
- `lab/cli.py`
- artifact retention policies if report files add new kinds

## Tasks

### F6.1 — Night session loop
Implement a bounded unattended loop that:
- runs preflight
- fills the queue if needed
- executes proposals until time/runs exhaust
- generates a final report
Acceptance:
- partial progress survives interrupt

### F6.2 — Daily report renderer
Generate Markdown and JSON report artifacts from DB + artifacts.

### F6.3 — Leaderboard renderer
Create campaign-local leaderboards ordered by policy-consistent metric/disposition.

### F6.4 — Champion cards
Write concise durable summaries for promoted/champion runs.

### F6.5 — Crash summary
Aggregate crash classes and include suppression suggestions.

### F6.6 — Recommendation section
Reports should suggest:
- next structured regions
- good ablations
- when a code proposal is justified
These recommendations may be heuristic; keep them simple and inspectable.

## Acceptance criteria

Phase 6 is complete when:

- `night` can run a fake or tiny session end-to-end
- a daily report is written to `artifacts/reports/<date>/`
- the report clearly identifies winners, losers, and failures
- leaderboard and champion artifacts are inspectable from the CLI

## Non-goals

Do **not** in Phase 6:
- build a dashboard web app
- hide the report logic behind opaque templating magic
