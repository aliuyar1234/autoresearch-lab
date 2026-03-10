# Lab CLI product spec

The CLI is the primary operator interface for the lab.
It must be usable from a terminal with no dashboard.

## Implementation choice

Use the Python standard library unless there is a compelling reason otherwise.
Prefer `argparse` over adding a large CLI dependency.

Module entry point:

- `python -m lab.cli ...`

## Top-level command groups

Required command groups for the current lab:

1. `bootstrap`
2. `preflight`
3. `smoke`
4. `campaign`
5. `run`
6. `autotune`
7. `inspect`
8. `replay`
9. `score`
10. `validate`
11. `noise`
12. `memory`
13. `export-code-proposal`
14. `import-code-proposal`
15. `night`
16. `report`
17. `doctor`
18. `cleanup`

The CLI may add aliases, but these names must exist.

## Global behaviors

### Global flags

All commands should support these where sensible:

- `--repo-root PATH`
- `--artifacts-root PATH`
- `--db-path PATH`
- `--worktrees-root PATH`
- `--cache-root PATH`
- `--json`
- `--verbose`

### Exit code policy

- `0` success
- `2` user or config error
- `3` preflight failure
- `4` run failure
- `5` schema validation failure
- `6` interrupted or partial

### Output policy

- human-readable text by default
- stable JSON when `--json` is supplied
- JSON must be machine-consumable and avoid mixed prose

## Command contracts

### 1. `bootstrap`

Purpose:

- create local directories
- initialize SQLite
- apply all tracked SQL migrations
- verify docs, schema, and SQL roots exist
- write a local `.lab.env` template if absent

Must:

- create `artifacts/`, `.worktrees/`, and configured cache dirs if missing
- initialize DB through the same multi-file migration path used by normal runtime commands
- print created and verified paths

### 2. `preflight`

Purpose:

- verify environment before expensive work

Must check:

- Python environment imports
- CUDA availability
- selected device info
- disk space in artifacts root
- DB readability and writability
- required campaign manifest exists
- required assets exist or identify what is missing
- backend selector can list candidates

Optional heavy check:

- `--benchmark-backends` reruns the backend microbench for the selected campaign shape family and refreshes cache state

### 3. `smoke`

Purpose:

- quick health check

`smoke` without `--gpu`:

- validates imports, DB, schemas, and CLI plumbing

`smoke --gpu`:

- runs a tiny real dense train and eval path
- prepares tiny real campaign assets under `artifacts/smoke/` when required
- fails if strict compiled training cannot complete on the selected backend

### 4. `campaign`

Subcommands:

- `list`
- `show`
- `build`
- `verify`
- `queue`

`build` must:

- materialize tokenizer and data assets
- write asset manifests and integrity hashes
- be idempotent

`verify` must:

- validate hashes
- confirm that required packed blocks and eval splits exist

`queue` should:

- preview scheduler-selected structured proposals from current campaign state
- optionally persist them as queued proposals when `--apply` is supplied
- remain deterministic for the same ledger and campaign state

### 5. `run`

Purpose:

- execute one experiment from a proposal

Accepted proposal inputs:

- `--proposal PATH`
- `--proposal-id ID`
- `--generate structured`

Must:

- create an experiment id before execution
- generate and persist structured proposals when requested
- materialize resolved `config.json`, `manifest.json`, and environment snapshots
- record artifacts and ledger rows
- persist explicit `eval_split` and `run_purpose`
- print experiment id, proposal id, proposal family and kind, validation state, and final disposition

### 6. `autotune`

Purpose:

- probe and cache runtime-only tuning overlays

Must:

- operate per campaign, lane, backend, and device profile
- choose runtime-only settings such as batch sizes or compile enablement
- preserve scientific identity while recording runtime overlay and effective runtime settings

### 7. `inspect`

Purpose:

- inspect a campaign, proposal, experiment, or related durable state

Must display:

- campaign metadata when `--campaign` is supplied
- archive snapshot and bucket membership when present
- queued proposal summary when present
- latest report metadata and artifact paths when present
- proposal family and kind
- final metrics
- validation state and linked review metadata when present
- runtime overlay and autotune metadata when present
- artifact paths and parent or child relationships when known

### 8. `replay`

Purpose:

- rerun an existing proposal or experiment manifest

Must:

- use the same campaign and proposal semantics unless explicit overrides are given
- produce a new experiment id
- record link to the source experiment

### 9. `score`

Purpose:

- recompute or inspect a scoring decision

Must show:

- raw metric delta
- disposition
- complexity tie-break explanation
- archive or champion effect
- validation state

### 10. `validate`

Purpose:

- run confirm, audit, or locked review replays for a candidate experiment

Must:

- accept `--experiment <id>` and `--mode confirm|audit|locked`
- persist validation review records
- reuse comparator replays when allowed
- gate promotions so raw wins do not become validated champions automatically

### 11. `noise`

Purpose:

- run comparable baseline probes to estimate metric spread

Must:

- accept campaign and lane
- produce machine-readable JSON and Markdown artifacts
- avoid changing the scientific proposal semantics

### 12. `memory`

Subcommands:

- `backfill`
- `inspect`

`backfill` must:

- derive memory records from historical ledger and artifact state
- preserve campaign scoping and comparability boundaries

`inspect` must:

- surface stored memory records, source kinds, and evidence-related metadata

### 13. `export-code-proposal`

Purpose:

- create a self-contained pack for an external coding agent

Output pack contents must include:

- proposal JSON
- target files
- parent commit
- acceptance criteria
- evidence context
- validation targets
- concise proposal context
- patch or worktree return instructions

### 14. `import-code-proposal`

Purpose:

- import a returned code-lane patch or worktree back into the lab

Must:

- accept `--proposal-id <id>` plus exactly one of `--patch-path` or `--worktree-path`
- validate the returned change against the proposal target-file allowlist
- store a durable imported bundle under proposal artifacts
- preserve lineage so the normal runner and memory ingestion can attribute the returned code correctly

### 15. `night`

Purpose:

- run an unattended multi-experiment session

Must:

- perform preflight first
- auto-resume proposals left in `running` state
- populate the proposal queue if empty
- run until time budget is exhausted or the queue drains
- emit a morning report at the end
- preserve partial progress on interrupt

### 16. `report`

Purpose:

- render a human-readable report from ledger and artifacts

Must produce:

- Markdown and JSON report artifacts
- companion artifacts for leaderboard, champion cards, and crash summary
- a daily report row in SQLite for later `inspect --campaign` lookup
- metrics including memory citation coverage, repeated-dead-end rate, and validation pass rate

### 17. `doctor`

Purpose:

- diagnose ledger and artifact health before or after unattended sessions

Must:

- run SQLite integrity checks
- detect missing retained artifacts
- detect missing report files
- warn on still-running proposals and broken or incomplete worktrees
- return machine-readable findings in `--json` mode

### 18. `cleanup`

Purpose:

- garbage-collect safe-to-delete lab outputs

Must:

- default to dry-run unless `--apply`
- show bytes and files by category
- never delete outside managed roots
- preserve champion, promoted, and report artifacts
- remove only `discardable` or `ephemeral` artifacts from the ledger and refresh per-run `artifact_index.json`

## Stability promise

The CLI is user-facing API.
Do not rename commands casually.
If arguments change, update:

- this spec
- tests
- `docs/runbook.md`
- any templates that reference them
