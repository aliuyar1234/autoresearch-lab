# Phase 1 — Runner, ledger, and artifact core

Status: planned

## Objective

Build the minimum credible lab core:
a real runner, a real SQLite ledger, and real per-experiment artifacts.

## Deliverables

1. experiment runner lifecycle
2. SQLite schema and data access layer
3. artifact writing and indexing
4. crash classification
5. fake-target integration tests
6. `run`, `inspect`, and partial `score` CLI support

## Exact files to create

Required new files:
- `lab/runner/__init__.py`
- `lab/runner/contracts.py`
- `lab/runner/execute.py`
- `lab/runner/failures.py`
- `lab/runner/materialize.py`
- `lab/ledger/__init__.py`
- `lab/ledger/db.py`
- `lab/ledger/queries.py`
- `lab/ledger/records.py`
- `lab/artifacts.py`
- `sql/001_ledger.sql`
- `schemas/run_manifest.schema.json`
- `schemas/experiment_record.schema.json`
- `schemas/artifact_index.schema.json`
- `tests/unit/test_failure_classification.py`
- `tests/integration/test_runner_success.py`
- `tests/integration/test_runner_failure.py`
- `tests/fixtures/fake_target_success.py`
- `tests/fixtures/fake_target_failure.py`

Required file updates:
- `lab/cli.py`

## Tasks

### F1.1 — SQLite initialization
Create schema migration loader for `sql/001_ledger.sql`.
Acceptance:
- bootstrap initializes DB
- rerun is idempotent
- schema version metadata is queryable

### F1.2 — Experiment record model
Define stable records for campaigns, proposals, experiments, artifacts, champions, reports.
Acceptance:
- rows can be inserted and queried without ad hoc SQL scattered everywhere

### F1.3 — Manifest materialization
Before launching a target:
- allocate experiment id
- write `manifest.json`
- snapshot proposal/config/env
Acceptance:
- manifest exists even if launch immediately fails

### F1.4 — Subprocess runner
Implement controlled subprocess execution with:
- explicit cwd
- explicit env
- stdout/stderr capture
- budget timeout
Acceptance:
- successful fake target yields completed terminal status
- timeout/failure yields failed terminal status

### F1.5 — Crash classification
Map common failure signatures to crash classes.
Acceptance:
- OOM, timeout, import error, assertion, and unknown are covered by tests

### F1.6 — Artifact index
Write `artifact_index.json` and keep it in sync with retained artifacts.

### F1.7 — Inspect command
`inspect` should show the important fields for an experiment or proposal.

### F1.8 — Preliminary score command
Allow score explanation for a single run even if the full promotion logic lands later.
Acceptance:
- can print raw metric and status from summary

## Acceptance criteria

Phase 1 is complete when:

- a fake successful run creates a DB row and artifact directory
- a fake failing run creates a DB row, terminal status, logs, and crash class
- `inspect` works on both successful and failed fake runs
- schema validation failures fail the run cleanly
- no control-path logic depends on grepping arbitrary logs

## Non-goals

Do **not** in Phase 1:
- build the full scheduler
- implement campaign asset builders
- fully refactor the research surface
- design final ranking logic beyond basic record/inspect support
