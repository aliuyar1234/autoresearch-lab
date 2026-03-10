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
uv sync
python -m lab.cli bootstrap
python -m lab.cli preflight
python -m lab.cli campaign build --campaign base_2k
python -m lab.cli run --campaign base_2k --generate structured --lane scout
python -m lab.cli night --campaign base_2k --hours 8 --allow-confirm
python -m lab.cli report --campaign base_2k
python -m lab.cli doctor
python -m lab.cli cleanup --dry-run
```

If a run looks promising, validate it before treating it as a champion:

```bash
python -m lab.cli validate --experiment <experiment_id> --mode confirm
python -m lab.cli validate --experiment <experiment_id> --mode audit
```

## Main Commands

Common path:

- `python -m lab.cli bootstrap`
- `python -m lab.cli preflight`
- `python -m lab.cli campaign build`
- `python -m lab.cli run`
- `python -m lab.cli night`
- `python -m lab.cli report`
- `python -m lab.cli doctor`
- `python -m lab.cli cleanup --dry-run`

Advanced:

- `python -m lab.cli inspect`
- `python -m lab.cli replay`
- `python -m lab.cli score`
- `python -m lab.cli validate`
- `python -m lab.cli noise`
- `python -m lab.cli autotune`
- `python -m lab.cli campaign queue`
- `python -m lab.cli campaign show`
- `python -m lab.cli campaign verify`
- `python -m lab.cli memory backfill`
- `python -m lab.cli memory inspect`
- `python -m lab.cli smoke --gpu`

## Code Lane

When structured search is not enough:

```bash
python -m lab.cli export-code-proposal --proposal-id <proposal_id>
python -m lab.cli import-code-proposal --proposal-id <proposal_id> --patch-path path\to\returned.patch
python -m lab.cli run --proposal-id <proposal_id>
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

Historical notes live under `docs/archive/` and `showcase/the-remembering-scientist/archive/`.

## Upstream Baseline

The minimal upstream-style path is still here:

```bash
uv run prepare.py
uv run train.py
```

That is useful for sanity checks and baseline parity work.

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
