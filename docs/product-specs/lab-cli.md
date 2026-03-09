# Lab CLI product spec

The CLI is the primary operator interface for the lab.
It must be usable from a terminal with no dashboard.

## Implementation choice

Use the Python standard library unless there is a compelling reason otherwise.
Prefer `argparse` over adding a large CLI dependency.

Module entry point:
- `python -m lab.cli ...`

Optional convenience:
- `uv run python -m lab.cli ...`

## Top-level command groups

Required command groups for v1:

1. `bootstrap`
2. `preflight`
3. `campaign`
4. `run`
5. `night`
6. `report`
7. `inspect`
8. `replay`
9. `export-code-proposal`
10. `import-code-proposal`
11. `score`
12. `cleanup`
13. `smoke`
14. `doctor`

The CLI may add aliases, but these names must exist.

## Global behaviors

### Global flags
All commands should support these where sensible:
- `--repo-root PATH`
- `--artifacts-root PATH`
- `--db-path PATH`
- `--json`
- `--verbose`

### Exit code policy
- `0` success
- `2` user/config error
- `3` preflight failure
- `4` run failure
- `5` schema validation failure
- `6` interrupted / partial

### Output policy
- Human-readable text by default
- Stable JSON when `--json` is supplied
- JSON must be machine-consumable and avoid mixed prose

## Command contracts

### 1. `bootstrap`
Purpose:
- create local directories
- initialize SQLite
- verify docs/schema/sql paths exist
- write a local `.lab.env` template if absent

Must:
- create `artifacts/`, `.worktrees/`, and configured cache dirs if missing
- initialize DB from `sql/001_ledger.sql`
- print created/verified paths

### 2. `preflight`
Purpose:
- verify environment before expensive work

Must check:
- Python environment imports
- CUDA availability
- selected device info
- disk space in artifacts root
- DB readability/writability
- required campaign manifest exists
- required assets exist or identify what is missing
- backend selector can list candidates

Optional heavy check:
- `--benchmark-backends` reruns the backend microbench for the selected campaign shape family and refreshes cache state

JSON output must include:
- `ok`
- `device`
- `cuda_version`
- `driver`
- `campaign_id`
- `missing_assets`
- `warnings`

### 3. `campaign`
Subcommands:
- `list`
- `show`
- `build`
- `verify`
- `queue`

`build` must:
- materialize tokenizer/data assets
- write asset manifests and integrity hashes
- be idempotent

`verify` must:
- validate hashes
- confirm that required packed blocks and eval splits exist

`queue` should:
- preview scheduler-selected structured proposals from current campaign state
- optionally persist them as queued proposals when `--apply` is supplied
- remain deterministic for the same ledger/campaign state

### 4. `run`
Purpose:
- execute one experiment from a proposal

Accepted proposal inputs:
- `--proposal PATH`
- `--proposal-id ID`
- `--generate structured`

Important:
- `--generate structured` means "generate a structured proposal"
- the generated proposal still needs a `family` such as `exploit`, `ablation`, or `novel`
- generated structured runs require `--campaign <campaign_id>` and `--lane scout|main|confirm`
- `--family baseline|exploit|ablation|combine|novel` may be supplied to force one family
- if `--family` is omitted, the scheduler selects a family from current campaign state

Must:
- create an experiment id before execution
- if generating, write the generated proposal snapshot under `artifacts/proposals/`
- materialize a resolved `config.json` snapshot for the run
- materialize a run manifest
- invoke the stable runner
- record artifacts and ledger rows
- print experiment id, proposal id, proposal family/kind, and final disposition

Default implementation choice:
- if no custom target command is supplied, `run` should call the repo-local dense trainer entry point with the resolved `config.json`

### 5. `night`
Purpose:
- run an unattended multi-experiment session

Must:
- perform preflight first
- auto-resume proposals that were left in `running` state
- populate proposal queue if empty
- run until time budget exhausted or queue drains
- emit a morning report at the end
- preserve partial progress on interrupt

Optional flags:
- `--hours`
- `--max-runs`
- `--mix structured:80 code:20`
- `--allow-confirm`
- `--seed-policy fixed|mixed`
- `--target-command` / `--target-command-json` for controlled fake or alternate targets

### 6. `report`
Purpose:
- render human-readable report from ledger + artifacts

Must produce:
- Markdown report always
- optional HTML if implemented
- path to generated report artifact
- companion artifacts for leaderboard, champion cards, and crash summary
- a daily report row in SQLite for later `inspect --campaign` lookup
- session notes when the report was emitted from an auto-resumed or interrupted `night` session

Supported report flags:
- `--campaign <campaign_id>` (required)
- `--date YYYY-MM-DD` to choose the report output date
- `--from <iso8601>` and `--to <iso8601>` to constrain the included run window

### 7. `inspect`
Purpose:
- inspect a campaign, proposal, or experiment

Must display:
- campaign metadata when `--campaign` is supplied
- archive snapshot / bucket membership when present
- queued proposal summary when present
- latest report metadata and artifact paths when present
- proposal metadata
- proposal family and kind
- final metrics
- artifact paths
- parent/child relationships if known

### 8. `replay`
Purpose:
- rerun an existing proposal or experiment manifest

Must:
- use the same campaign/proposal/config unless explicit overrides are given
- produce a new experiment id
- record link to the source experiment

### 9. `export-code-proposal`
Purpose:
- create a self-contained pack for an external coding agent

Output pack contents:
- proposal JSON
- target files
- parent commit
- acceptance criteria
- minimal repo context summary
- patch return instructions

The exported pack must not require reading chat history.
Current implementation exports proposals with `kind = code_patch`.

### 10. `import-code-proposal`
Purpose:
- import a returned code-lane patch or worktree back into the lab

Must:
- accept `--proposal-id <id>` plus exactly one of `--patch-path` or `--worktree-path`
- validate the returned change against the proposal target-file allowlist
- store a durable imported bundle under proposal artifacts
- update proposal metadata so the normal runner can execute the imported result from an isolated snapshot

### 11. `score`
Purpose:
- recompute or inspect a scoring decision

Must show:
- raw metric delta
- promotion decision
- complexity tie-break explanation
- archive/champion effect

### 12. `cleanup`
Purpose:
- garbage-collect safe-to-delete lab outputs

Must:
- default to dry-run unless `--apply`
- show bytes/files by category
- never delete outside managed roots
- preserve champion/promoted/report artifacts
- remove only `discardable` / `ephemeral` artifacts from the ledger and refresh per-run `artifact_index.json`

### 13. `smoke`
Purpose:
- quick health check

`smoke` without `--gpu`:
- validates imports, DB, schemas, CLI plumbing

`smoke --gpu`:
- runs tiny preflight
- tiny backend check
- tiny real dense train/eval path
- prepares tiny real campaign assets under `artifacts/smoke/` when required
- fails if strict compiled training cannot complete on the selected backend

### 14. `doctor`
Purpose:
- diagnose ledger/artifact health before or after unattended sessions

Must:
- run SQLite integrity checks
- detect missing retained artifacts
- detect missing report files
- warn on still-running proposals and broken/incomplete worktrees
- return machine-readable findings in `--json` mode

## Stability promise

The CLI is user-facing API.
Do not rename commands casually.
If arguments change, update:
- this spec
- tests
- runbook
- any templates that reference them
