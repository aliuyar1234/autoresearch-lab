# Phase 7 — Reliability, cleanup, and final polish

Status: complete

## Objective

Harden the lab into something that deserves unattended use.

## Deliverables

1. resume/recovery logic
2. cleanup / garbage collection
3. stronger crash diagnostics
4. final smoke commands
5. final docs alignment and quality scoring update
6. regression checklist and release readiness notes

## Exact files to create

Required new files:
- `lab/resume.py`
- `lab/cleanup.py`
- `lab/doctor.py`
- `tests/unit/test_cleanup_policy.py`
- `tests/integration/test_resume_queue.py`
- `tests/gpu/test_smoke_cli.py`

Required file updates:
- `lab/cli.py`
- reports to reflect resumed/interrupted sessions
- docs/runbook
- `docs/QUALITY_SCORE.md`

## Tasks

### F7.1 — Resume logic
On restart, reconstruct in-progress queue/session state from SQLite and artifacts.
Acceptance:
- interrupted fake session can continue without losing previous experiments

### F7.2 — Conservative cleanup
Implement dry-run and apply modes.
Acceptance:
- cleanup never deletes champion/promoted/report artifacts
- cleanup never leaves DB pointing at missing retained artifacts

### F7.3 — Doctor diagnostics
Add a `doctor` or extended `preflight` path for:
- DB integrity
- missing artifact detection
- broken symlink/worktree detection
- schema drift warnings

### F7.4 — Crash exemplar retention
Retain representative failure artifacts for the top crash classes.

### F7.5 — Final smoke
Ensure there is a documented smoke path for:
- CPU/no-GPU structural validation
- GPU tiny run
- report generation

### F7.6 — Final polish
Update docs, quality score, and any templates that drifted during implementation.

## Acceptance criteria

Phase 7 is complete when:

- queue/session resume works after interruption
- cleanup can safely prune discardable artifacts
- `smoke` and `smoke --gpu` are documented and pass
- docs, schemas, and tests match the implementation
- the repo feels like a real lab, not a stitched-together prototype

## Completion notes

Implemented in repo:
- `lab/resume.py` reconstructs interrupted proposal state from SQLite plus run artifacts and requeues orphaned work safely
- `lab/cleanup.py` performs conservative dry-run/apply pruning for `discardable` and `ephemeral` artifacts only
- `lab/doctor.py` checks DB integrity, retained artifact/report presence, running proposal state, and worktree hygiene
- `lab/code_proposals.py` now supports importing returned code-lane patches/worktrees and executing them from isolated snapshots
- `night` now resumes interrupted state before execution and emits report session notes for resumed/interrupted sessions
- Phase 7 tests cover cleanup policy, doctor detection, resumed queue execution, and GPU smoke CLI behavior

## Non-goals

Do **not** in Phase 7:
- start a new architecture initiative
- land speculative model changes unrelated to reliability/polish
