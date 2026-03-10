# Resolved ambiguities

This file records important design decisions that remove ambiguity.

It starts with the decisions already made in the patched pack.
Future implementation-forced changes should be appended here with date, reason, and scope.

## Initial resolved decisions

### A1 — Proposal taxonomy has two axes
Reason:
Earlier docs could be read as if proposal intent and proposal implementation mode were the same thing.

Resolution:
- `family`: baseline / exploit / ablation / combine / novel / manual
- `kind`: structured / code_patch / manual

### A2 — Crash class uses `interrupted`
Reason:
Earlier docs mixed `keyboard_interrupt` and `interrupted`.

Resolution:
Use `interrupted` everywhere.

### A3 — Base 2k parity campaign uses explicit held-out shards
Resolution:
- search validation shard: `shard_06542.parquet`
- audit validation shard: `shard_06541.parquet`
- locked validation shard: `shard_06540.parquet`
- training excludes those explicit shards

### A4 — Long 4k is campaign-local, not globally comparable
Resolution:
`long_4k` uses the climbmix source family but is not leaderboard-comparable to `base_2k`.

### A5 — Stories campaign uses deterministic partitioning
Resolution:
TinyStories-style campaign splits are deterministic hash partitions, not ad hoc sampling.

### A6 — Control plane is structured data
Resolution:
runner, scheduler, promotion, archive, and reporting must use structured JSON and SQLite.
Raw logs are debugging artifacts only.

### A7 — Backend choice is cached and blacklist-aware
Resolution:
backend microbench results are cached by device profile and shape family.
Runtime failures can blacklist backend-shape pairs and trigger reselection.

### A8 — Reference implementations are normative starting points
Resolution:
For scheduler, archive, promotion, packing, crash classification, and recommendations, `reference_impl/` is the intended implementation scaffold.

### A9 â€” Report artifacts use date-first then campaign paths
Reason:
The artifact contract wanted date-local reports, while the path helper and multi-campaign behavior still required a campaign dimension.

Resolution:
- report bundles live under `artifacts/reports/<date>/<campaign_id>/`
- `report_root(paths, campaign_id, report_date)` resolves to that date-first layout
- `inspect --campaign` surfaces the latest report bundle for that campaign

### A10 - Reliability diagnostics use a standalone `doctor` command, and `night` auto-resumes first
Reason:
Phase 7 allowed either an extended `preflight` path or a separate doctor flow, and it did not pin down when interrupted queue repair should happen.

Resolution:
- `python -m lab.cli doctor` is the canonical retained-artifact / DB-integrity diagnostic entry point
- `night` calls resume logic before preflight and execution
- resumed or interrupted night sessions add session notes to the generated report bundle

### A11 - Code-lane round-trip imports patch files or worktree paths
Reason:
The acceptance matrix required importing returned code proposals, but the earlier implementation only exported packs and did not define the concrete return format supported by the CLI.

Resolution:
- `python -m lab.cli import-code-proposal` is the canonical return path
- current direct import support accepts `--patch-path` and `--worktree-path`
- imported code proposals execute from an isolated snapshot under `.worktrees/`, while main repo state remains untouched

### A12 - Promotion requires validation, not just a strong confirm run
Reason:
Earlier docs and mental models could still be read as if a strong confirm-lane result promoted directly.

Resolution:
- raw search outcomes and validated champions are distinct states
- candidates may remain `pending_validation`
- only passed validation reviews count as promoted champions

### A13 - Runtime autotune changes execution overlays only
Reason:
Autotune introduces runtime variability, but the repo still needs scientific identity to remain comparable.

Resolution:
- autotune may choose runtime-only overlays such as batch sizes or compile enablement
- scientific identity remains tied to the proposal and resolved scientific config
- manifests and reports must surface both runtime overlay and effective runtime settings explicitly

## How to extend this file

Append entries in this format:

- id
- date
- phase
- decision
- reason
- affected files
