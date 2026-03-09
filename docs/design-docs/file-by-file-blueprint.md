# File-by-file blueprint

This document tells Codex what each major file or package is supposed to do.

It is intentionally concrete because vague “subsystem” language leads to drift.

## Root-level files

### `AGENTS.md`
Repository-local operating instructions.

### `ARCHITECTURE.md`
Top-level architecture map and invariants.

### `CODEX_GUARDRAILS.md`
Anti-drift constraints and wrong-turn prevention.

### `docs/`
Human-readable product memory.
The repo should remain understandable from here.

### `schemas/`
Machine-checkable JSON contracts.
These are not suggestions.

### `sql/`
SQLite schema and migrations.

### `templates/`
Campaign and report templates.

## `lab/` package

The stable operating system of the lab.

### `lab/__init__.py`
No side effects.
Expose package version only if useful.

### `lab/version.py`
A tiny version constant or helper.

### `lab/settings.py`
Responsibilities:
- load settings from CLI args, env, `.lab.env`, and defaults
- define a `LabSettings` dataclass
- resolve repo root and managed paths
- validate dangerous path escapes

Must not:
- perform heavy I/O on import
- mutate directories on import

### `lab/paths.py`
Responsibilities:
- compute all managed roots
- create directories on demand
- provide helper functions for artifact, report, campaign-cache, and worktree paths

Recommended functions:
- `discover_repo_root()`
- `build_paths(settings)`
- `ensure_managed_roots(paths)`
- `experiment_root(paths, experiment_id)`
- `report_root(paths, campaign_id, report_date)`

### `lab/cli.py`
Responsibilities:
- only CLI argument parsing and command dispatch
- no business logic hidden here
- every subcommand calls a smaller function in the appropriate module

Required command groups:
- bootstrap
- preflight
- campaign
- run
- night
- report
- inspect
- replay
- export-code-proposal
- score
- cleanup
- smoke

### `lab/preflight.py`
Responsibilities:
- environment checks
- CUDA/device inspection
- campaign manifest existence
- disk-space checks
- schema/sql existence
- backend candidate list
- JSON-serializable result object

### `lab/contracts.py`
Recommended central place for:
- dataclasses shared across modules
- `ExperimentSummary`
- `RunManifest`
- `ArtifactRecord`
- `ProposalRecord`
- `CampaignRecord`
- `ReportRecord`

Keep this thin.
Do not create a giant type-theory layer.

## `lab/runner/`

### `lab/runner/__init__.py`
Minimal exports.

### `lab/runner/contracts.py`
Runner-local dataclasses and enums:
- lifecycle states
- crash classes
- runner result

### `lab/runner/materialize.py`
Responsibilities:
- allocate experiment id
- create run directory
- write manifest, config snapshot, env snapshot, proposal snapshot
- create initial artifact index

### `lab/runner/failures.py`
Responsibilities:
- classify crash excerpts
- map subprocess outcomes to crash class
- normalize terminal failure structure

Use `reference_impl/crash_classifier.py`.

### `lab/runner/execute.py`
Responsibilities:
- construct subprocess command
- set cwd and env
- stream/capture stdout/stderr
- enforce timeout
- detect summary file
- call schema validation
- update ledger

Must not:
- contain scheduler logic
- parse random log text to infer metrics if a summary exists

### `lab/runner/checkpointing.py`
Recommended helper for:
- pre-eval checkpoint policy
- retention metadata

### `lab/runner/replay.py`
Responsibilities:
- recreate a run from a proposal or manifest with a new experiment id

## `lab/ledger/`

### `lab/ledger/db.py`
SQLite connection helpers and migration application.

### `lab/ledger/queries.py`
Small query functions or methods.
No huge ORM.

### `lab/ledger/records.py`
Mapping from dataclasses to row dictionaries and back.

### `lab/ledger/archive.py`
Optional but recommended:
- champion/near-miss persistence helpers
- archive bucketing helpers

## `lab/backends/`

### `lab/backends/profiles.py`
Device profile definitions and normalization.

### `lab/backends/selector.py`
Backend selection logic and cache lookup.

### `lab/backends/benchmark.py`
Microbench harness.
Should be easy to rerun and record.

### `lab/backends/cache.py`
JSON cache for backend choices and blacklists.

Use `reference_impl/backend_selector.py`.

## `lab/campaigns/`

### `lab/campaigns/load.py`
Load and validate campaign manifests.

### `lab/campaigns/build.py`
Top-level asset build orchestration.

### `lab/campaigns/verify.py`
Hash/integrity checks and manifest validation.

### `lab/campaigns/builders/base_2k.py`
Exact builder for base 2k parity campaign.

### `lab/campaigns/builders/stories_2k.py`
Builder for TinyStories-style fast campaign.

### `lab/campaigns/builders/long_4k.py`
Builder for long-context campaign.

### `lab/campaigns/packing.py`
Offline packer orchestration.
Should call a pure packing function and write manifests.

Use:
- `reference_impl/offline_packing.py`
- `reference_impl/campaign_split_rules.py`

## `lab/scheduler/`

### `lab/scheduler/generate.py`
Proposal generation:
- baseline
- exploit
- ablation
- combine
- novel
- code exports

### `lab/scheduler/select.py`
Choose what to run next from queue plus archive state.

### `lab/scheduler/promote.py`
Lane advancement and champion decisions.

### `lab/scheduler/archive.py`
Maintain champion, pareto, simplicity, and near-miss buckets.

### `lab/scheduler/novelty.py`
Coverage tracking and novelty tags.

### `lab/scheduler/compose.py`
Combine orthogonal winning changes into new proposals.

Use:
- `reference_impl/scheduler_policy.py`
- `reference_impl/promotion_policy.py`
- `reference_impl/archive_policy.py`

## `lab/reports/`

### `lab/reports/daily.py`
Build the morning report JSON model.

### `lab/reports/render.py`
Render Markdown and optional HTML from the report JSON.

### `lab/reports/leaderboard.py`
Campaign-local leaderboard generation.

### `lab/reports/champion.py`
Champion cards.

### `lab/reports/crashes.py`
Crash summaries.

### `lab/reports/recommend.py`
Inspectable recommendation heuristics.

Use `reference_impl/report_recommendations.py`.

## `lab/utils/`

Small boring helpers only:

- JSON read/write
- hashing
- timestamps
- filesystem helpers
- schema validation helpers

Avoid turning `utils` into a junk drawer.

## `research/dense_gpt/`

This is the mutable research surface.

### `research/dense_gpt/defaults.py`
Canonical default knobs and grouped config structure.

### `research/dense_gpt/model.py`
Dense model architecture.

### `research/dense_gpt/optim.py`
Optimizer groups and schedules.

### `research/dense_gpt/train.py`
One experiment entry point.
Must emit a machine-readable summary.

### `research/dense_gpt/search_space.py`
Structured knobs and valid mutation ranges.

### `research/dense_gpt/mutation_rules.py`
Mutation operators and legality constraints.

### `research/dense_gpt/fingerprint.py`
Deterministic config fingerprinting if not shared from `lab/`.

## `campaigns/`

Committed human-readable campaign manifests.
Do not hide campaign semantics in code only.

## `tests/`

### `tests/unit/`
Pure logic tests:
- settings
- path safety
- fingerprinting
- crash classification
- scheduler decisions
- promotion rules

### `tests/integration/`
End-to-end fake-target tests:
- runner success/failure
- DB writes
- artifact creation
- report generation
- campaign build/verify

### `tests/gpu/`
Tiny but real GPU checks.
Keep these small and explicit.

### `tests/fixtures/`
Fake targets and sample JSON contracts.
The pack now includes some of these.

## `reference_impl/`

Reference algorithms for the hardest parts.

These are starting points and guardrails.
They are deliberately concrete so that Codex does not invent a weaker version of the lab.
