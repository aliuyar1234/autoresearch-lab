# Autoresearch Lab

![teaser](progress.png)

Autoresearch Lab is a local, single-GPU, CUDA-first, dense-model research lab built on top of Andrej Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch).

It keeps the original "run real training loops overnight" spirit, but adds the parts a serious lab needs: campaigns, SQLite state, explicit evaluation splits, validation reviews, evidence-traced memory, runtime autotune, code-lane round trips, reports, recovery tooling, and a reproducible showcase path.

## What It Is

- single GPU only
- CUDA first
- dense-model first
- local artifacts and local SQLite control plane
- validated champions, not raw search winners
- stable lab layer plus hackable research surface

The main boundary is:

- stable lab infrastructure in `lab/`, `campaigns/`, `schemas/`, `sql/`
- mutable research surface in `research/dense_gpt/`, `train.py`, and code proposals

## Current Capabilities

- multi-file SQL migrations
- campaign-aware asset building and split management
- explicit `search_val`, `audit_val`, and `locked_val`
- confirm/audit validation ladder
- evidence-traced memory and retrieval lineage
- archive-aware scheduler with repeated-dead-end tracking
- runtime-only autotune overlays
- code proposal export/import with lineage preserved
- unattended `night` sessions with morning reports
- remembering-vs-amnesiac showcase automation

## Quick Start

Requirements:

- one NVIDIA GPU
- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)

```bash
uv sync --group dev
uv run arlab bootstrap
uv run arlab preflight
uv run arlab campaign build --campaign base_2k
uv run arlab run --campaign base_2k --generate structured --lane scout
uv run arlab night --campaign base_2k --hours 8 --allow-confirm
uv run arlab report
uv run arlab doctor
uv run arlab cleanup --dry-run
```

If a run looks promising, validate it before treating it as a champion:

```bash
uv run arlab validate --experiment <experiment_id> --mode confirm
uv run arlab validate --experiment <experiment_id> --mode audit
```

## Main Commands

Common path:

- `uv run arlab bootstrap`
- `uv run arlab preflight`
- `uv run arlab campaign build`
- `uv run arlab run`
- `uv run arlab night`
- `uv run arlab report`
- `uv run arlab doctor`
- `uv run arlab cleanup --dry-run`

Advanced:

- `uv run arlab inspect`
- `uv run arlab replay`
- `uv run arlab score`
- `uv run arlab validate`
- `uv run arlab noise`
- `uv run arlab autotune`
- `uv run arlab campaign queue`
- `uv run arlab campaign show`
- `uv run arlab campaign verify`
- `uv run arlab memory backfill`
- `uv run arlab memory inspect`
- `uv run arlab smoke --gpu`

Fallback:

- `uv run python -m lab.cli ...` remains supported when you explicitly want module invocation.

## Code Lane

When structured search is not enough:

```bash
uv run arlab export-code-proposal --proposal-id <proposal_id>
uv run arlab import-code-proposal --proposal-id <proposal_id> --patch-path path\to\returned.patch
uv run arlab run --proposal-id <proposal_id>
```

The exported pack includes:

- proposal json
- task summary
- local contracts
- acceptance criteria
- evidence citations
- validation targets
- concise proposal context
- exact target files
- return instructions

Imported code proposals execute from an isolated snapshot under `.worktrees/` and then flow through the same runner, scoring, archive, memory, and report path as structured proposals.

## Showcase

The flagship showcase is `The Remembering Scientist`.

Core claim:

`Same GPU. Same campaign. Same budget. The only intended difference is memory.`

Start here:

- [SHOWCASE.md](SHOWCASE.md)
- [showcase/the-remembering-scientist/README.md](showcase/the-remembering-scientist/README.md)
- `python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json`

Historical notes live under `docs/archive/` and `showcase/the-remembering-scientist/archive/`.

## Upstream Baseline

The minimal upstream-style path is still here:

```bash
uv run prepare.py
uv run train.py
```

That is useful for sanity checks and baseline parity work.

Archived upstream materials live under `docs/archive/upstream-baseline/`.

## Docs

Read these first:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/runbook.md`
- `docs/RELIABILITY.md`
- `docs/SECURITY.md`
- `SHOWCASE.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`

## License

MIT
