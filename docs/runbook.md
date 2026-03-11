# Runbook

This runbook is the operator guide for Autoresearch Lab as it exists now.

## 0. Learn the golden path first

If you only need one path through the repo, use this one:

```bash
uv sync --group dev
uv run arlab bootstrap
uv run arlab preflight --campaign base_2k --benchmark-backends
uv run arlab campaign build --campaign base_2k
uv run arlab autotune --campaign base_2k --all-lanes
uv run arlab night --campaign base_2k --hours 8 --allow-confirm
uv run arlab report --campaign base_2k
uv run arlab inspect --campaign base_2k
uv run arlab doctor
```

Everything else in this runbook is secondary to that path.

## 1. Bootstrap a fresh clone

```bash
git clone https://github.com/aliuyar1234/autoresearch-lab.git
cd autoresearch-lab
uv sync --group dev
uv run arlab bootstrap
uv run arlab preflight --campaign base_2k --benchmark-backends
uv run arlab smoke --gpu
uv run arlab doctor
```

Expected outcome:

- managed roots created
- SQLite initialized and all `sql/*.sql` migrations applied in order
- machine and environment summary printed
- optional backend benchmarks cached when requested
- `doctor` reports no retained-artifact or DB-integrity errors

## 2. Understand state roots and migrations

Important paths:

- ledger: `lab.sqlite3` by default, or `--db-path`
- artifacts: `artifacts/` by default, or `--artifacts-root`
- worktrees: `.worktrees/` by default, or `--worktrees-root`
- runtime cache: `artifacts/cache/` by default, or `--cache-root`

Migration behavior:

- commands apply all SQL files under `sql/` lexicographically
- applied versions are tracked in `schema_migrations`
- directory-mode migrations are the normal operating mode, not a bootstrap-only special case

## 3. Build campaign assets

`base_2k` is the canonical campaign.

```bash
uv run arlab campaign list
uv run arlab campaign show --campaign base_2k
uv run arlab campaign build --campaign base_2k
uv run arlab campaign verify --campaign base_2k
```

Expected outputs:

- tokenizer assets
- pretokenized shards
- packed blocks
- integrity manifests
- explicit `search_val`, `audit_val`, and `locked_val` split definitions

Current canonical-path truth:

- the builder expects local UTF-8 source files under the campaign raw cache root
- the builder writes deterministic byte-fallback tokenizer assets
- `prepare.py` remains the upstream truth anchor for parquet + BPE semantics

## 4. Warm runtime autotune

```bash
uv run arlab autotune --campaign base_2k --all-lanes
```

What it does:

- probes runtime-only settings such as device batch size, eval batch size, and compile enablement
- caches winners by campaign, lane, backend, and device profile
- preserves scientific identity while changing only execution overlays

## 5. Run one structured experiment

```bash
uv run arlab run --campaign base_2k --generate structured --lane scout
uv run arlab inspect --experiment <experiment_id>
uv run arlab score --experiment <experiment_id>
```

Look for:

- experiment id
- proposal family and kind
- resolved `config.json` and `manifest.json`
- runtime overlay and autotune metadata
- terminal summary status
- primary metric, validation state, and disposition

## 6. Validate a promising candidate

Strong search results are not automatically champions.

```bash
uv run arlab validate --experiment <experiment_id> --mode confirm
uv run arlab validate --experiment <experiment_id> --mode audit
```

Look for:

- confirm and audit review records in SQLite
- replay experiment ids
- median candidate and comparator metrics
- `pending_validation` turning into `promoted` only after confirm passes

To estimate baseline noise:

```bash
uv run arlab noise --campaign base_2k --lane scout --count 5
```

## 7. Run a bounded overnight session

```bash
uv run arlab night --campaign base_2k --hours 8 --allow-confirm
uv run arlab report --campaign base_2k
uv run arlab inspect --campaign base_2k
```

Expected outputs:

- multiple experiment artifact directories
- updated SQLite ledger
- auto-resume of any proposals left in `running` state from a previous interrupted session
- report bundle under `artifacts/reports/<date>/<campaign_id>/`
- leaderboard, champion-card, crash summary, and report JSON/Markdown pairs

The report should surface:

- validated promotions, not just raw highs
- memory citation coverage
- repeated-dead-end rate
- validation pass rate
- recommendations and latest champion context

This is the official endurance proof path for the lab itself.

## 8. Inspect or backfill memory

```bash
uv run arlab memory inspect --campaign base_2k --limit 20
uv run arlab memory backfill --campaign base_2k
```

Use these when:

- older ledger state needs memory records generated retroactively
- you want to inspect cited memories, retrieval events, and source kinds directly

## 9. Export and import a code proposal pack

Use this only when structured search is not enough.

```bash
uv run arlab export-code-proposal --proposal-id <proposal_id>
uv run arlab import-code-proposal --proposal-id <proposal_id> --patch-path path\\to\\returned.patch
uv run arlab run --proposal-id <proposal_id>
```

The exported pack should include:

- proposal json
- task summary
- local contracts
- acceptance criteria
- target file list
- `context/evidence.json`
- `context/validation_targets.json`
- `context/proposal_context.md`
- return instructions

Current direct import support accepts:

- patch files
- worktree paths

Imported code proposals execute from an isolated snapshot under `.worktrees/` and then flow through the same runner, memory, scoring, archive, and report path as structured proposals.

## 10. Run the showcase pipeline

The flagship showcase is scriptable, but it is a secondary proof path on top of the lab.

```bash
python showcase/the-remembering-scientist/freeze_memory_snapshot.py --campaign base_2k --source-db <workspace>/lab.sqlite3 --output-root showcase/the-remembering-scientist/01_seed_snapshot
python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm
python showcase/the-remembering-scientist/run_validations.py --campaign base_2k --output-root showcase/the-remembering-scientist
python showcase/the-remembering-scientist/render_case_study.py --campaign base_2k --output-root showcase/the-remembering-scientist
python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json
```

Expected outputs:

- frozen memory snapshot manifest
- remembering and amnesiac pair roots
- `compare.json` and `compare.md`
- confirm, audit, and replay artifacts under `validations/`
- figure-input JSON under `figures/`
- `CASE_STUDY_DRAFT.md`

This is the official showcase proof path.

## 11. Cleanup and recovery

Always start with dry-run:

```bash
uv run arlab cleanup --dry-run
```

Then apply if the plan looks safe:

```bash
uv run arlab cleanup --apply
```

The cleanup command must never delete:

- champion artifacts
- promoted artifacts
- reports
- campaign assets
- any path outside managed roots
- crash exemplars for failed runs

For interruption recovery:

```bash
uv run arlab doctor --json
uv run arlab night --campaign base_2k --hours 8 --allow-confirm
```

Look for:

- `missing_artifact`
- `missing_report_artifact`
- `proposal_still_running`
- DB integrity errors

## 12. Lightweight final signoff

The lightweight signoff path is:

```bash
python tools/ten_of_ten_signoff.py --json
uv run python tools/parity_harness.py --json
```

That script intentionally avoids GPU-heavy end-to-end checks. It runs:

- lightweight repo sanity checks
- lightweight CLI bootstrap and doctor checks in an isolated temp root
- one report generation pass
- a curated subset of roadmap tests

The human-facing rubric lives in:

- `docs/OPERATING_CONTRACT.md`
- `docs/RESEARCH_CONTRACT.md`
- `docs/AGENT_SESSION_CONTRACT.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`

Fallback:

- `uv run python -m lab.cli ...` remains supported when you explicitly want module invocation.

## 13. Merge readiness checklist

Before calling the lab "done enough to defend":

- baseline parity path still exists for `base_2k`
- `docs/OPERATING_CONTRACT.md`, `docs/RESEARCH_CONTRACT.md`, and `docs/AGENT_SESSION_CONTRACT.md` still match the live repo
- fake and integration tests pass
- GPU smoke passes on the target machine
- validated champions are distinguishable from raw search wins
- memory citations and repeated-dead-end metrics appear in reports
- at least one code proposal pack can be exported and round-tripped
- showcase automation runs from code
- `doctor` returns clean output for the repo env
- front-door docs, schemas, and the signoff matrix all match implementation reality
