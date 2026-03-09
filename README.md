# Autoresearch Lab

![teaser](progress.png)

Autoresearch Lab is an enhanced, research-infrastructure-focused version of Andrej Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch).

The original repo is a compact idea: let an agent iterate on a real single-GPU training setup overnight. This repo keeps that spirit, but turns it into a more complete local research lab with campaigns, structured proposals, SQLite memory, artifact hygiene, scheduler/archive logic, code-lane round trips, morning reports, and recovery tooling.

In one sentence:

**Autoresearch Lab is a single-GPU, CUDA-first, dense-model research lab built on top of the original `autoresearch` concept.**

## What changed from upstream

This repo is no longer just "edit `train.py` and see what happens."

It adds a stable lab layer around the research surface:

- a real CLI in `lab/cli.py`
- SQLite-backed experiment, proposal, champion, and report memory
- campaign-local data assets and comparability boundaries
- structured proposal generation and queueing
- promotion rules, archive buckets, and leaderboard/champion views
- unattended `night` sessions that end in a morning report
- conservative cleanup, crash diagnostics, and resume-after-interruption logic
- a code lane that can export a code proposal pack, import a returned patch/worktree, and run it through the normal scoring path

The result is closer to "a personal one-GPU research organization" than a minimal training toy.

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
python -m lab.cli run --campaign base_2k --generate structured --lane scout
python -m lab.cli night --campaign base_2k --hours 8 --allow-confirm
python -m lab.cli report --campaign base_2k
python -m lab.cli inspect --campaign base_2k
```

What this gives you:

- reproducible campaign assets
- durable run artifacts under `artifacts/`
- ledger state in SQLite
- scheduler-selected proposals instead of manual guessing
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
```

Then run one experiment:

```bash
python -m lab.cli run --campaign base_2k --generate structured --lane scout
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
- `python -m lab.cli replay`
- `python -m lab.cli score`
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
- `docs/product-specs/acceptance-matrix.md`

## Relationship to upstream

This project is best understood as:

- inspired by Karpathy's `autoresearch`
- still single-GPU and dense-model focused
- intentionally much more structured and operational

If upstream is the seed idea, this repo is the "make it into a serious local lab" version.

## License

MIT
