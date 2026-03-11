# Agent Session Contract

This document defines the machine-readable contract for long autonomous agent work.

Use it together with:

- `docs/OPERATING_CONTRACT.md`
- `docs/RESEARCH_CONTRACT.md`
- `docs/runbook.md`

## Session As First-Class Unit

The lab now treats one multi-hour autonomous run as a first-class session.

The session is the right unit for answering:

- what budget the agent had
- what lanes it used
- how many structured runs and code runs it spent
- where it switched lanes
- what it concluded before stopping
- what policy suggestion it left behind

## Official Session Artifacts

For each `arlab night` session, the repo writes:

- `artifacts/reports/_sessions/<campaign_id>/<session_id>/session_manifest.json`
- `artifacts/reports/_sessions/<campaign_id>/<session_id>/checkpoints/checkpoint_###.json`
- `artifacts/reports/_sessions/<campaign_id>/<session_id>/retrospective.json`

The ledger also persists:

- `agent_sessions`
- `agent_session_events`

## Session Manifest

`session_manifest.json` is the main machine-readable artifact for an agent.

It contains:

- `session`
- `session_notes`
- `executed`
- `checkpoint_paths`
- `report_json_path`
- `retrospective_json_path`

The `session` object includes:

- `session_id`
- `campaign_id`
- `status`
- `stop_reason`
- `hours_budget`
- `max_runs_budget`
- `max_structured_runs_budget`
- `max_code_runs_budget`
- `run_count`
- `structured_run_count`
- `code_run_count`
- `confirm_run_count`
- `queue_refills`
- `self_review_count`
- `report_checkpoint_count`
- `lane_switch_count`
- `active_scheduler_policy`
- `draft_scheduler_policy_path`

## Checkpoints

Checkpoints are lightweight self-review artifacts written during a session.

Each checkpoint includes:

- strongest surviving candidates
- strongest rejected candidates
- top failures
- current lane mix

They are intended for:

- an autonomous agent revising its own plan mid-session
- a human quickly auditing what the agent thinks is happening

## Retrospective

`retrospective.json` is the final session-level conclusion.

It is not a promotion artifact by itself.
It is a navigation artifact for the next loop.

It contains:

- session summary
- current best candidate
- strongest surviving candidates
- strongest rejected candidates
- top failures
- next actions
- lane comparison
- memory policy summary

## Scheduler Policy Contract

The lab can load one reviewed scheduler policy from:

- `artifacts/policies/<campaign_id>/active_reviewed_policy.json`

That file must match:

- `schemas/agent_scheduler_policy.schema.json`

Important rule:

- draft policy suggestions may be generated automatically
- only reviewed policies may influence queue refill behavior

This keeps the lab agent-first without letting the scheduler become silently self-deceptive.

## Hard Invariants

These remain hard even for strong agents:

- comparability
- lineage
- validation gates
- honest naming
- isolated code execution

The session layer exists to increase autonomy, not to weaken trust.
