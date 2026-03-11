# Operating Contract

This document defines the repo's main operating path.

Autoresearch Lab is not a platform and not a generalized MLOps layer.
It is Karpathy's `autoresearch`, turned into a real local single-GPU research operating system.

## One-Sentence Identity

**Autoresearch Lab is a local single-GPU research operating system that preserves Karpathy's overnight experiment-loop spirit while adding durable state, validation, reports, and recovery.**

## Golden Operator Path

This is the main path that the repo should optimize for and defend first:

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

If a candidate matters, validate it explicitly:

```bash
uv run arlab validate --experiment <experiment_id> --mode confirm
uv run arlab validate --experiment <experiment_id> --mode audit
```

Everything else is secondary until this path is healthy.

## Canonical Campaign

`base_2k` is the canonical campaign.

Why this campaign is canonical:

- it preserves the upstream 2048 context target
- it preserves the upstream 8192 vocab target
- it preserves the upstream 300-second main-run budget
- it is the campaign the repo should use for parity language, trust claims, and endurance testing

### What Is Real

- local UTF-8 source files under `raw_cache_root`
- explicit `search_val`, `audit_val`, and `locked_val`
- deterministic byte-fallback tokenizer assets written by the builder
- local manifests for raw files, tokenizer assets, pretokenized assets, and packed blocks
- validation-gated promotion

### What Is Heuristic

- runtime autotune overlays
- scheduler family choice and archive reuse
- memory retrieval ranking
- report recommendations

### What Is Baseline-Only

- direct parquet download and tokenizer training in `prepare.py`
- the original direct upstream training loop in `train.py`

### What Is Experimental Or Secondary

- showcase A/B memory claims
- code proposal lane
- non-canonical campaigns such as `stories_2k` and `long_4k`

## Official Proof Paths

There are exactly two official proof paths.

### 1. Official Lab Endurance Run

This proves the lab as a tool:

```bash
uv run arlab night --campaign base_2k --hours 8 --allow-confirm
uv run arlab report --campaign base_2k
uv run arlab inspect --campaign base_2k
uv run arlab doctor --json
uv run python tools/ten_of_ten_signoff.py --json
```

Expected proof:

- multiple bounded runs complete
- the ledger remains coherent
- reports distinguish raw highs from validated outcomes
- doctor remains clean
- signoff stays green

### 2. Official Showcase Proof Path

This proves one bounded public capability story on top of the lab:

```bash
python showcase/the-remembering-scientist/freeze_memory_snapshot.py --campaign base_2k --source-db <workspace>/lab.sqlite3 --output-root showcase/the-remembering-scientist/01_seed_snapshot
python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm
python showcase/the-remembering-scientist/run_validations.py --campaign base_2k --output-root showcase/the-remembering-scientist
python showcase/the-remembering-scientist/render_case_study.py --campaign base_2k --output-root showcase/the-remembering-scientist
python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json
```

Expected proof:

- a complete compare bundle exists
- validations and rendered artifacts exist
- the verifier returns `ok: true`

## Failure Honesty

The lab is allowed to say:

- the run completed, but the hypothesis did not hold
- the raw winner did not survive validation
- the showcase was healthy even if the headline arm lost

The repo becomes less trustworthy, not more, if it hides those outcomes.

## Secondary Paths

These are real, but secondary:

- `uv run arlab export-code-proposal ...`
- `uv run arlab import-code-proposal ...`
- `uv run arlab memory inspect ...`
- `uv run arlab memory backfill ...`
- `uv run arlab noise ...`
- `uv run python -m lab.cli ...`

They should never become easier to understand than the golden path.
