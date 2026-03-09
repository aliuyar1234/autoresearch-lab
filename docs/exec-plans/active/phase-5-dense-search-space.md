# Phase 5 — Dense search surface and backend integration

Status: completed

## Objective

Make the dense-model structured search space genuinely rich while integrating the backend selector and device-profile-aware runtime behavior.

## Deliverables

1. structured dense-model defaults
2. mutation rules and legality constraints
3. backend selection and cache
4. device profile support
5. tiny GPU smoke path
6. tests for structured search and backend behavior

## Exact files to create

Required new files:
- `lab/backends/__init__.py`
- `lab/backends/profiles.py`
- `lab/backends/selector.py`
- `lab/backends/benchmark.py`
- `lab/backends/cache.py`
- `research/dense_gpt/__init__.py`
- `research/dense_gpt/defaults.py`
- `research/dense_gpt/model.py`
- `research/dense_gpt/optim.py`
- `research/dense_gpt/train.py`
- `research/dense_gpt/search_space.py`
- `research/dense_gpt/mutation_rules.py`
- `research/dense_gpt/fingerprint.py`
- `tests/unit/test_search_space.py`
- `tests/unit/test_backend_selector.py`
- `tests/gpu/test_tiny_gpu_run.py`

Required file updates:
- `lab/cli.py`
- campaign manifests if device/backend metadata changes materially

## Required references

Read before implementing:
- `docs/design-docs/model-search-space.md`
- `docs/design-docs/runtime-and-gpu.md`
- `docs/product-specs/device-profiles.md`
- `reference_impl/backend_selector.py`
- `reference_impl/config_fingerprint.py`

## Tasks

### F5.1 — Structured defaults
Implement dense-model defaults as grouped config, not loose globals.

### F5.2 — Search-space legality
Expose mutation ranges for:
- depth
- width/aspect
- head dimension
- kv head ratio
- window pattern
- optimizer group knobs
- weight decay groups
- RoPE base
- EMA
- progressive depth
- sequence curriculum

### F5.3 — Device profiles
Implement explicit device profile selection and persistence.

### F5.4 — Backend selector
Implement correctness check, microbench, cache, and blacklist behavior.

### F5.5 — Summary contract
Ensure every tiny real run records:
- backend
- device profile
- config fingerprint
- primary metric
- throughput metrics

## Acceptance criteria

Phase 5 is complete when:

- structured mutation surface exists
- backend choices are cached by device profile and shape family
- tiny GPU smoke runs emit valid summaries
- search surface is richer than upstream without becoming a framework

## Validation

Implemented and verified in the repo:
- `lab/backends/` now provides device profiles, cached backend selection, blacklist persistence, and rerunnable microbench selection.
- `research/dense_gpt/` now provides grouped defaults, legality checks, mutation rules, fingerprinting, a compact dense model, grouped optimizer, and a real tiny train/eval entry point.
- `lab/cli.py`, `lab/preflight.py`, `lab/runner/execute.py`, `lab/runner/materialize.py`, and `lab/scheduler/generate.py` are wired to the new search space and backend selector.
- Phase 5 tests now exist in `tests/unit/test_search_space.py`, `tests/unit/test_backend_selector.py`, and `tests/gpu/test_tiny_gpu_run.py`.
- Verification:
  - `python -m unittest discover -s tests -p "test_*.py"`
  - `python tools/spec_lint.py`

## Non-goals

Do **not** in Phase 5:
- add MoE, routers, or distributed code
- hide backend behavior behind opaque abstractions
