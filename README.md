# Autoresearch Lab

![teaser](progress.png)

Autoresearch Lab is a local, research-infrastructure-focused evolution of Andrej Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch).

The original repo is a compact idea: let an agent iterate on a real single-GPU training setup overnight. This repo keeps that spirit, but turns it into a more complete local research lab with multi-file migrations, explicit eval splits, a validation ladder, evidence-traced memory, runtime autotune, code-lane round trips, morning reports, and showcase automation.

In one sentence:

**Autoresearch Lab is a single-GPU, CUDA-first, dense-model research lab with validated champions, evidence memory, and reproducible operator workflows.**

## Showcase

The public showcase materials now have two layers:

- [SHOWCASE.md](SHOWCASE.md)
- [showcase/the-remembering-scientist/README.md](showcase/the-remembering-scientist/README.md)

`SHOWCASE.md` is the bounded public pilot writeup. The showcase directory contains the reproducible pipeline that can:

- freeze a historical memory snapshot
- run remembering-vs-amnesiac A/B pairs with isolated roots
- generate confirm, audit, and replay artifacts
- render figure-input JSON and a case-study draft from stored outputs

The flagship claim stays the same:

- same GPU
- same campaign
- same bounded search budget
- remembering vs amnesiac lab state

The current public writeup is intentionally caveated. The pilot is promising, but still honest about confirm noise and what has not yet been proven.

## What changed from upstream

This repo is no longer just "edit `train.py` and see what happens."

It adds a stable lab layer around the research surface:

- a real CLI in `lab/cli.py`
- multi-file SQL migrations tracked in SQLite
- SQLite-backed experiment, proposal, validation, evidence, champion, and report memory
- campaign-local data assets and comparability boundaries
- structured proposal generation and queueing
- explicit `search_val`, `audit_val`, and `locked_val` evaluation splits
- a validation ladder where strong search results become `pending_validation` until review passes
- evidence-traced retrieval memory with citation coverage and repeated-dead-end metrics
- runtime-only autotune overlays cached by lane, backend, and device profile
- unattended `night` sessions that end in a morning report
- conservative cleanup, crash diagnostics, and resume-after-interruption logic
- a code lane that can export an evidence-grounded code proposal pack, import a returned patch/worktree, and run it through the normal scoring path
- showcase automation for `The Remembering Scientist`

The result is closer to "a personal one-GPU research organization" than a minimal training toy.

## Validated champions, not raw search wins

This repo deliberately separates a promising search result from a validated champion.

- search runs can produce strong raw candidates
- strong confirm-lane search results become `pending_validation`
- `python -m lab.cli validate --experiment <id> --mode confirm` is the step that decides promotion
- only passed validation reviews count as validated champions

That rule matters for both reports and public claims.

## Project shape

The repo has two layers:

### 1. Stable lab infrastructure

This is the part meant to stay legible and dependable:

- `lab/`
- `campaigns/`
- `schemas/`
- `sql/`
- `docs/`
- `reference_impl/`
- `showcase/`

### 2. Mutable research surface

This is the part meant to be explored:

- `research/dense_gpt/`
- `train.py`
- campaign-specific config/search knobs
- code proposal packs

## Core workflow

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

What this gives you:

- reproducible campaign assets
- durable run artifacts under `artifacts/`
- ledger state in SQLite
- scheduler-selected proposals instead of manual guessing
- explicit validation state for raw wins versus promoted champions
- memory citations, repeated-dead-end metrics, and validation pass rate in reports
- a report bundle you can read in the morning

## Quick start

Requirements:

- one NVIDIA GPU
- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)

Recommended setup:

```bash
# 1. Install dependencies
uv sync

# 2. Initialize the lab
python -m lab.cli bootstrap

# 3. Build campaign assets
python -m lab.cli campaign build --campaign base_2k

# 4. Verify the machine and repo
python -m lab.cli preflight --campaign base_2k --benchmark-backends
python -m lab.cli smoke --gpu
python -m lab.cli doctor

# 5. Optional but recommended: warm runtime autotune
python -m lab.cli autotune --campaign base_2k --all-lanes
```

Then run one experiment:

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

## Code-lane workflow

When structured search is not enough, the lab can open a code lane:

```bash
python -m lab.cli export-code-proposal --proposal-id <proposal_id>
python -m lab.cli import-code-proposal --proposal-id <proposal_id> --patch-path path\to\returned.patch
python -m lab.cli run --proposal-id <proposal_id>
```

The exported pack now includes:

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

Imported code proposals execute from an isolated snapshot under `.worktrees/` and then go through the same runner, scoring, archive, and report path as structured proposals.

## Important commands

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

## If you want the original minimal path

The upstream-style baseline path is still here:

```bash
uv run prepare.py
uv run train.py
```

That is useful for sanity checks and baseline parity work.

## Docs to read first

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/PLANS.md`
- `docs/runbook.md`
- `docs/product-specs/lab-cli.md`
- `docs/product-specs/code-lane-evidence-contract.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`
- `showcase/the-remembering-scientist/README.md`

## Relationship to upstream

This project is best understood as:

- inspired by Karpathy's `autoresearch`
- still single-GPU and dense-model focused
- intentionally much more structured and operational

If upstream is the seed idea, this repo is the "make it into a serious local lab" version.

## License

MIT
