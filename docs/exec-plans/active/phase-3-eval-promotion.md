# Phase 3 — Evaluation ladder, scoring, and replay

Status: planned

## Objective

Make experiment promotion, replay, and checkpoint-before-eval behavior real.

## Deliverables

1. scoring logic
2. scout/main/confirm decision path
3. replay support
4. checkpoint-before-eval handling
5. score explanation CLI
6. tests for promotion decisions

## Exact files to create

Required new files:
- `lab/scoring.py`
- `lab/replay.py`
- `tests/unit/test_promotion_policy.py`
- `tests/integration/test_replay_and_score.py`

Required file updates:
- `lab/cli.py`
- `lab/runner/execute.py`
- `docs/product-specs/runner-contract.md`

## Required references

Read before implementing:
- `docs/design-docs/evaluation-and-scoring.md`
- `docs/design-docs/algorithmic-appendix.md`
- `reference_impl/promotion_policy.py`

## Tasks

### F3.1 — Rule-based score explanation
Implement score explanation that reports:
- baseline metric
- candidate metric
- delta
- threshold
- complexity tie-break effect
- final disposition

### F3.2 — Promotion ladder
Implement:
- scout to main
- main to confirm
- confirm to promoted/champion/archive

### F3.3 — Replay
Allow a proposal or experiment manifest to be replayed with a new experiment id.

### F3.4 — Checkpoint-before-eval
Before expensive final evaluation, save a checkpoint when the run is eligible.
Acceptance:
- if final eval crashes, the run is still auditable and recoverable

## Acceptance criteria

Phase 3 is complete when:

- `score` can explain promotion decisions
- `replay` creates a new linked experiment
- checkpoint-before-eval behavior exists and is visible in artifacts
- lane-specific thresholds are enforced by code, not prose alone

## Non-goals

Do **not** in Phase 3:
- build the full scheduler
- add fuzzy weighted-score optimization
