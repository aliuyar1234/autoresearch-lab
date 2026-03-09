# Phase 4 — Scheduler, archive, and proposal system

Status: completed

## Objective

Turn the lab from a single-run executor into a real research engine with proposal generation, queue selection, archive maintenance, and code-proposal export.

## Deliverables

1. proposal generator with explicit families
2. queue selection policy
3. elite archive
4. promotion handoff hooks
5. code-proposal export
6. scheduler tests

## Exact files to create

Required new files:
- `lab/scheduler/__init__.py`
- `lab/scheduler/generate.py`
- `lab/scheduler/select.py`
- `lab/scheduler/archive.py`
- `lab/scheduler/compose.py`
- `lab/scheduler/novelty.py`
- `tests/unit/test_scheduler_policy.py`
- `tests/unit/test_archive_policy.py`
- `tests/integration/test_export_code_proposal.py`

Required file updates:
- `lab/cli.py`
- `lab/ledger/queries.py`
- `schemas/proposal.schema.json`
- `sql/001_ledger.sql`

## Required references

Before implementing this phase, read:
- `docs/design-docs/research-engine.md`
- `docs/design-docs/algorithmic-appendix.md`
- `docs/design-docs/codex-drift-risks.md`
- `reference_impl/scheduler_policy.py`
- `reference_impl/archive_policy.py`
- `reference_impl/promotion_policy.py`

## Tasks

### F4.1 — Proposal taxonomy
Implement proposal records with both:
- `family`
- `kind`

Acceptance:
- structured exploit, structured novel, manual baseline, and code-patch proposals can all be represented without ambiguity

### F4.2 — Structured proposal generator
Generate proposals from at least these families:
- baseline
- exploit
- ablation
- combine
- novel

Acceptance:
- generator never emits duplicate config fingerprints
- generator respects campaign constraints and guardrails

### F4.3 — Queue selection
Implement queue ranking and next-run selection.
Acceptance:
- baseline wins when absent
- repeated crash storms suppress unsafe proposal generation
- ablation is preferred after complex wins
- combine is chosen when orthogonal wins exist
- novelty is chosen when coverage is poor

### F4.4 — Elite archive
Maintain archive buckets:
- champions
- pareto
- near-misses
- novel winners

Acceptance:
- archive survives multiple runs
- archive is campaign-local
- archive buckets are visible to reports and scheduler

### F4.5 — Code proposal export
Implement `export-code-proposal`.
Acceptance:
- exported pack contains proposal JSON, target file allowlist, acceptance criteria, concise context, and return instructions
- exported pack does not require chat history

### F4.6 — Ledger integration
Persist enough metadata for reports and replay:
- family
- kind
- parent ids
- complexity cost
- archive status

## Acceptance criteria

Phase 4 is complete when:

- scheduler can fill a queue from current campaign state
- queue ranking is deterministic
- exported code proposal packs are self-sufficient
- archive buckets are inspectable
- no proposal field is overloaded with two meanings

## Non-goals

Do **not** in Phase 4:
- build an LLM-powered scheduler
- add a generic workflow engine
- hide scheduling rules in prompts alone
