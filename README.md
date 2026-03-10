# Autoresearch Lab

![teaser](progress.png)

Autoresearch Lab is a local, single-GPU, CUDA-first, dense-model research lab built on top of Andrej Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch).

It keeps the original spirit of "let the machine search overnight on a real training loop", but it is no longer a minimal hill-climber. It is a structured lab with campaigns, explicit evaluation splits, a validation ladder, evidence-traced memory, runtime autotune, code-lane round trips, morning reports, and a reproducible public showcase pipeline.

**In one sentence: Autoresearch Lab is a single-GPU, CUDA-first, dense-model research lab with validated champions, evidence memory, and operator-grade workflows.**

## Current State

This repo is past the "interesting prototype" stage. The current system includes:

- multi-file SQL migrations and a SQLite control plane
- campaign-aware dataset and split management
- structured proposal generation with archive-aware scheduling
- explicit `search_val`, `audit_val`, and `locked_val` evaluation behavior
- a real validation ladder so raw wins do not promote directly
- evidence-traced memory with citation coverage and repeated-dead-end tracking
- runtime-only autotune overlays cached by lane, backend, and device profile
- evidence-grounded code proposal export/import
- unattended `night` sessions with report bundles in the morning
- a scriptable remembering-vs-amnesiac showcase pipeline
- final signoff docs and a lightweight signoff script

## What Makes It Different

This repo is not just "edit `train.py` and hope."

It separates the project into two layers:

### Stable lab layer

The stable lab layer is the operating system of the repo:

- `lab/`
- `campaigns/`
- `schemas/`
- `sql/`
- `docs/`
- `reference_impl/`
- `showcase/`

This is where the runner, ledger, reports, scheduler, validation, memory, and reliability logic live.

### Mutable research surface

The mutable research surface is where the actual research changes happen:

- `research/dense_gpt/`
- `train.py`
- campaign-specific config/search knobs
- code proposal packs

This boundary is deliberate: the lab should stay trustworthy while the model surface stays hackable.

## Validated Champions, Not Raw Search Wins

One of the most important repo-level rules is that a promising search result is not the same thing as a validated champion.

- search runs can produce strong raw candidates
- strong candidates can become `pending_validation`
- `python -m lab.cli validate --experiment <id> --mode confirm` is the promotion gate
- only passed validation reviews count as promoted champions

That distinction shows up in the ledger, reports, and public showcase story.

## Showcase

The flagship showcase is `The Remembering Scientist`.

The public-facing materials live in:

- [SHOWCASE.md](SHOWCASE.md)
- [showcase/the-remembering-scientist/README.md](showcase/the-remembering-scientist/README.md)

The core claim is simple:

`Same GPU. Same campaign. Same budget. The only difference was memory.`

The showcase pipeline can:

- freeze a historical memory snapshot
- run remembering-vs-amnesiac A/B pairs with isolated roots
- generate confirm, audit, and replay artifacts
- render figure-input JSON and a case-study draft from stored outputs

## Core Workflow

The main operator loop is:

```bash
python -m lab.cli bootstrap
python -m lab.cli preflight --campaign base_2k
python -m lab.cli campaign build --campaign base_2k
python -m lab.cli autotune --campaign base_2k --all-lanes
python -m lab.cli run --campaign base_2k --generate structured --lane scout
python -m lab.cli validate --experiment <experiment_id> --mode confirm
python -m lab.cli night --campaign base_2k --hours 8 --allow-confirm
python -m lab.cli report --campaign base_2k
python -m lab.cli inspect --campaign base_2k
```

What that gives you:

- reproducible campaign assets
- durable run artifacts under `artifacts/`
- ledger state in SQLite
- scheduler-selected proposals instead of manual guessing
- explicit validation state for raw wins versus promoted champions
- memory citations, repeated-dead-end metrics, and validation pass rate in reports
- a report bundle you can read in the morning

## Quick Start

Requirements:

- one NVIDIA GPU
- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)

Recommended setup:

```bash
uv sync
python -m lab.cli bootstrap
python -m lab.cli campaign build --campaign base_2k
python -m lab.cli preflight --campaign base_2k --benchmark-backends
python -m lab.cli smoke --gpu
python -m lab.cli doctor
python -m lab.cli autotune --campaign base_2k --all-lanes
```

Then run one structured experiment:

```bash
python -m lab.cli run --campaign base_2k --generate structured --lane scout
```

If a run looks promising, validate it before treating it as a champion:

```bash
python -m lab.cli validate --experiment <experiment_id> --mode confirm
python -m lab.cli validate --experiment <experiment_id> --mode audit
```

Or run an unattended session:

```bash
python -m lab.cli night --campaign base_2k --hours 8 --allow-confirm
```

## Code Lane

When structured search is not enough, the lab can open a code lane:

```bash
python -m lab.cli export-code-proposal --proposal-id <proposal_id>
python -m lab.cli import-code-proposal --proposal-id <proposal_id> --patch-path path\to\returned.patch
python -m lab.cli run --proposal-id <proposal_id>
```

The exported pack includes:

- proposal json
- target file list
- base commit
- acceptance criteria
- evidence citations
- validation targets
- concise proposal context
- return instructions

Current direct import support accepts:

- patch files
- worktree paths

Imported code proposals execute from an isolated snapshot under `.worktrees/` and then flow through the same runner, memory, scoring, archive, and report path as structured proposals.

## Important Commands

- `python -m lab.cli bootstrap`
- `python -m lab.cli preflight`
- `python -m lab.cli campaign build`
- `python -m lab.cli campaign queue`
- `python -m lab.cli run`
- `python -m lab.cli validate`
- `python -m lab.cli noise`
- `python -m lab.cli autotune`
- `python -m lab.cli replay`
- `python -m lab.cli score`
- `python -m lab.cli memory backfill`
- `python -m lab.cli memory inspect`
- `python -m lab.cli export-code-proposal`
- `python -m lab.cli import-code-proposal`
- `python -m lab.cli night`
- `python -m lab.cli report`
- `python -m lab.cli inspect`
- `python -m lab.cli cleanup`
- `python -m lab.cli doctor`
- `python -m lab.cli smoke --gpu`

## If You Want The Original Minimal Path

The upstream-style baseline path is still here:

```bash
uv run prepare.py
uv run train.py
```

That is useful for sanity checks and baseline parity work.

## Docs To Read First

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/PLANS.md`
- `docs/runbook.md`
- `docs/product-specs/lab-cli.md`
- `docs/product-specs/code-lane-evidence-contract.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`
- `showcase/the-remembering-scientist/README.md`

## Relationship To Upstream

This project is best understood as:

- inspired by Karpathy's `autoresearch`
- still single-GPU and dense-model focused
- intentionally much more structured and operational

If upstream is the seed idea, this repo is the "make it into a serious local lab" version.

## License

MIT
