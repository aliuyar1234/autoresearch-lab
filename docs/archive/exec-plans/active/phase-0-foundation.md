# Phase 0 — Foundation and repository operating system

Status: planned

## Objective

Lay down the durable skeleton of the lab without breaking baseline behavior.

This phase does **not** build the full lab.
It creates the knowledge store, path/settings system, minimal CLI skeleton, and test scaffolding that later phases depend on.

## Deliverables

1. repository scaffolding under `lab/` and `tests/`
2. path and settings utilities
3. minimal CLI entry point with `bootstrap`, `preflight`, and `smoke`
4. config/env loading strategy
5. managed local roots (`artifacts/`, `.worktrees/`, caches)
6. baseline-preserving project structure and docs integration
7. spec-lint utility for repo-local contract hygiene

## Exact files to create

Required new files:
- `lab/__init__.py`
- `lab/version.py`
- `lab/settings.py`
- `lab/paths.py`
- `lab/cli.py`
- `lab/preflight.py`
- `lab/utils/__init__.py`
- `lab/utils/fs.py`
- `lab/utils/json_io.py`
- `lab/utils/hash.py`
- `lab/utils/time.py`
- `tools/spec_lint.py`
- `tests/unit/test_settings.py`
- `tests/unit/test_paths.py`
- `tests/integration/test_cli_help.py`

Likely file updates:
- `.gitignore`
- `pyproject.toml` (only if minimal dependencies must be added)
- any baseline docs that need links to the new CLI entry point

## Required references

Read before implementing:
- `CODEX_GUARDRAILS.md`
- `docs/design-docs/file-by-file-blueprint.md`
- `docs/design-docs/codex-drift-risks.md`

## Tasks

### F0.1 — Establish package skeleton
Create the `lab/` package and import-safe module boundaries.
Acceptance:
- `python -c "import lab"` works
- no side effects on import

### F0.2 — Implement path registry
Create a single source of truth for important repo paths:
- repo root
- docs root
- artifacts root
- worktrees root
- DB path
- schemas root
- sql root
Acceptance:
- path helpers work from any working directory inside the repo
- tests cover directory creation

### F0.3 — Implement settings loader
Define settings precedence:
1. explicit CLI args
2. environment variables
3. optional `.lab.env`
4. safe defaults

Acceptance:
- missing optional settings use safe defaults
- required runtime settings fail with clear errors

### F0.4 — CLI skeleton
Implement a stable `python -m lab.cli` entry point with:
- help text
- `bootstrap`
- `preflight`
- `smoke`

Acceptance:
- `--help` works
- subcommand help works
- JSON mode works for `preflight`

### F0.5 — Bootstrap behavior
`bootstrap` must:
- create managed directories
- initialize the SQLite DB if missing
- refuse to create paths outside repo unless explicitly configured
Acceptance:
- rerunning `bootstrap` is idempotent

### F0.6 — Preflight baseline checks
Implement non-invasive checks:
- imports
- CUDA visibility
- disk space
- write access to artifact root
- campaign manifest existence if requested
Acceptance:
- returns structured JSON
- does not mutate campaign assets

### F0.7 — Spec lint
Implement `tools/spec_lint.py`.
Acceptance:
- validates required docs/specs/schemas exist
- validates JSON parses
- catches known placeholder tokens in committed repo knowledge files

### F0.8 — Test harness
Set up basic test layout and a tiny integration test around CLI help and settings/path behavior.

### F0.9 — Documentation sync
Update docs if the practical CLI or file names differ from the spec.
This phase should leave docs and code aligned.

## Acceptance criteria

Phase 0 is complete when:

- `python -m lab.cli bootstrap` succeeds on a clean clone
- `python -m lab.cli preflight --json` emits valid JSON
- `python tools/spec_lint.py` passes
- managed roots exist after bootstrap
- tests for settings and paths pass
- baseline top-level `prepare.py` / `train.py` are still untouched and runnable

## Non-goals

Do **not** in Phase 0:
- implement the full runner
- implement scheduler logic
- refactor the trainer into many files
- change the baseline training behavior
- add large dependencies

## Notes for Codex

Keep this phase boring.
The best outcome is a solid foundation, not visible novelty.
