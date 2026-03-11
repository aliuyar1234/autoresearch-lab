# Ten of Ten signoff

This document is the final human-readable signoff rubric for Autoresearch Lab.

It exists for one reason: to make it hard to confuse "lots of features" with "software we can actually trust."

## How to use this

Before shipping, publishing, or calling the project complete:

1. run the lightweight signoff script
2. review the 10 areas below
3. only mark a row complete when the cited evidence exists in code, tests, or stored artifacts

Recommended command:

```bash
python tools/ten_of_ten_signoff.py --json
```

## The ten checks

### 1. Identity is honest

- [ ] `pyproject.toml`, `README.md`, `AGENTS.md`, and `ARCHITECTURE.md` describe the repo as `Autoresearch Lab`
- [ ] no key metadata still describes the project as a generic swarm or upstream clone
- [ ] one golden operator path is obvious from the repo front door

### 2. Migrations are real

- [ ] the repo uses additive SQL files under `sql/`
- [ ] `schema_migrations` proves which versions were applied
- [ ] bootstrap and normal commands both rely on the same migration path

### 3. Scientific correctness is explicit

- [ ] `eval_split` is persisted per run
- [ ] `run_purpose` is persisted per run
- [ ] `search_val`, `audit_val`, and `locked_val` are campaign-level concepts, not hidden convention
- [ ] the canonical campaign does not claim a more realistic data/tokenizer path than the builder actually materializes

### 4. Validation is the promotion gate

- [ ] raw highs can stay `pending_validation`
- [ ] confirm reviews exist as durable records
- [ ] promoted champions are traceable to passed validation reviews

### 5. Memory is evidence-first

- [ ] proposals can cite memory ids directly
- [ ] retrieval events are stored
- [ ] reports surface citation coverage rather than implying memory influence indirectly

### 6. Scheduler memory is not naive

- [ ] composition has explicit parents
- [ ] repeated dead ends are tracked
- [ ] archive and scheduler state can explain why a family is being revisited or avoided

### 7. Runtime tuning is separated from science

- [ ] autotune caches runtime-only overlays
- [ ] effective runtime settings are visible in manifests and reports
- [ ] scientific identity does not silently change when runtime tuning changes

### 8. Code lane is grounded

- [ ] exported code proposal packs include evidence and validation context
- [ ] returned patches or worktrees preserve lineage
- [ ] imported code runs become first-class experiments with normal reporting and memory ingestion
- [ ] code lane stays secondary to the golden operator path

### 9. Showcase is reproducible

- [ ] the remembering-scientist pipeline can be run from code
- [ ] compare, validation, replay, and figure-input artifacts are generated from stored state
- [ ] `tools/verify_showcase_bundle.py` can mechanically verify the published bundle
- [ ] public showcase text does not depend on hand-assembled numbers

### 10. The repo can defend its claims

- [ ] docs, schemas, tests, and code tell the same story
- [ ] the runbook reflects actual commands
- [ ] the acceptance matrix is still true
- [ ] a new operator could understand what counts as proof from the repo alone
- [ ] `tools/parity_harness.py` reports the current upstream-vs-lab contract honestly

## Lightweight evidence pack

The signoff is strongest when you can point to:

- `docs/product-specs/acceptance-matrix.md`
- `docs/OPERATING_CONTRACT.md`
- `docs/RESEARCH_CONTRACT.md`
- `docs/AGENT_SESSION_CONTRACT.md`
- `docs/runbook.md`
- `showcase/the-remembering-scientist/README.md`
- `uv run python tools/parity_harness.py --json`
- `python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json`
- report JSON/Markdown under `artifacts/reports/`
- validation reviews in SQLite
- a green run of `python tools/ten_of_ten_signoff.py --json`

## What should block signoff

Do not sign off if any of these are true:

- docs still describe direct promotion from raw search wins
- memory influence is still mostly narrative instead of cited
- autotune changes scientific semantics
- code lane exports context-poor packs
- showcase outputs depend on fake placeholders
- the repo still needs hidden chat context to be understood
