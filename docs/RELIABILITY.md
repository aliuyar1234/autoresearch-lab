# RELIABILITY.md

## Reliability thesis

A research lab that loses a night of work to a late crash is not a lab.
It is a demo.

## Reliability goals

1. cleanly classify all failed runs
2. never lose experiment metadata
3. preserve artifacts even on failure
4. checkpoint before expensive final eval
5. resume queue execution after process restart
6. keep worktrees and artifact directories consistent

## Minimum reliability bar

The following must be true for the final system:

- every run gets an experiment id before execution starts
- every run writes a manifest before training starts
- every run ends in a terminal status
- every failed run has a crash class and error excerpt
- pre-eval checkpoint exists for long enough to support recovery
- a restart can reconstruct queue state from SQLite + artifacts

## Crash classes

Use at least these classes:

- `preflight_failed`
- `import_error`
- `compile_error`
- `oom_train`
- `oom_eval`
- `timeout`
- `nan_or_inf`
- `assertion_failure`
- `data_missing`
- `asset_corrupt`
- `backend_unavailable`
- `interrupted`
- `unknown`

## Retention rules

Keep:
- summary JSON
- manifest JSON
- stdout/stderr
- tail excerpt
- config snapshot
- patch diff
- checkpoint metadata
- proposal payload

Delete aggressively only:
- old temporary worktrees
- stale prepacked scratch files
- expired checkpoints not referenced by champions or reports

## Resilience strategy

- SQLite is the truth for run state
- artifacts are append-only per experiment id
- reports are derivable from ledger + artifacts
- cleanup must be conservative

## Overnight bar

Before calling the project done, it should be able to run a meaningful overnight queue and produce a coherent report with no manual artifact cleanup required.
