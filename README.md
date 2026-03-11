# Autoresearch Lab

![teaser](progress.png)

Autoresearch Lab is Andrej Karpathy's [`autoresearch`](https://github.com/karpathy/autoresearch), turned into a real local single-GPU research operating system.

It keeps the original "run real training loops overnight" spirit, but adds the machinery a serious one-workstation lab needs: campaigns, SQLite state, explicit evaluation splits, validation reviews, reports, recovery tooling, and reproducible proof paths.

The repo is also now agent-first in one important way: `night` sessions are first-class machine-readable autonomy units with budgets, checkpoints, retrospectives, and reviewed scheduler-policy hooks.

The repo's structure is intentional:

- the upstream baseline path stays alive as a truth anchor
- the lab-native path is the normal operator path
- the showcase is a secondary proof path, not the identity of the repo

## What It Is

- single GPU only
- CUDA first
- dense-model first
- local-first and repository-local
- not a platform, not distributed infrastructure
- local artifacts and local SQLite control plane
- validated champions, not raw search winners
- stable lab layer plus hackable research surface
- one canonical campaign and one canonical operator path
- one upstream truth anchor and one lab-native execution path

The main boundary is:

- stable lab infrastructure in `lab/`, `campaigns/`, `schemas/`, `sql/`
- mutable research surface in `research/dense_gpt/`, `train.py`, and code proposals

## Golden Path

If you only learn one path through the repo, learn this one:

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

If a result matters, validate it before speaking confidently about it:

```bash
uv run arlab validate --experiment <experiment_id> --mode confirm
uv run arlab validate --experiment <experiment_id> --mode audit
```

`base_2k` is the canonical campaign and `arlab` is the public front door.

If you want an explicitly agent-budgeted session instead of the plain endurance path:

```bash
uv run arlab night --campaign base_2k --hours 8 --allow-confirm --max-runs 12 --max-structured-runs 10 --max-code-runs 2 --self-review-every-runs 3
```

That session will leave a session manifest, checkpoints, and a retrospective under `artifacts/reports/_sessions/...`.

## Core Lab Capabilities

- multi-file SQL migrations
- campaign-aware asset building and split management
- explicit `search_val`, `audit_val`, and `locked_val`
- confirm/audit validation ladder
- evidence-traced memory and retrieval lineage
- archive-aware scheduler with repeated-dead-end tracking
- runtime-only autotune overlays
- unattended `night` sessions with morning reports
- first-class agent sessions with checkpoints and retrospectives
- full reports, doctoring, and cleanup

## Secondary Paths

These are real and supported, but secondary to the golden path:

- code proposal export/import with lineage preserved
- remembering-vs-amnesiac showcase automation
- memory inspection and backfill
- noise estimation and GPU smoke helpers
- `uv run python -m lab.cli ...` when you explicitly want module invocation

## Showcase

The flagship showcase is `The Remembering Scientist`, but it is a secondary proof path on top of the lab, not the identity of the repo.

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

Use `uv run python tools/parity_harness.py --json` to report the current parity contract between the upstream path and the lab-native path.

Archived upstream materials live under `docs/archive/upstream-baseline/`.

## Docs

Read these first:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/OPERATING_CONTRACT.md`
- `docs/RESEARCH_CONTRACT.md`
- `docs/AGENT_SESSION_CONTRACT.md`
- `docs/runbook.md`
- `docs/RELIABILITY.md`
- `docs/SECURITY.md`
- `SHOWCASE.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`

## License

MIT
