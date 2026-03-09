# ARCHITECTURE.md

This document is the top-level architectural map for Autoresearch Lab.

## Architectural statement

Autoresearch Lab is a **single-process, single-user, single-GPU, repository-local research system**.

It is not a service mesh.
It is not a distributed platform.
It is not an experiment tracker bolt-on.
It is a local research lab with strong internal structure.

## Architectural goals

1. preserve the upstream repo's hackability
2. add a real infrastructure layer around experiments
3. keep the runtime understandable from repo-local docs
4. support both structured and code-level research loops
5. optimize for one powerful CUDA workstation
6. produce durable artifacts and reproducible experiment history

## Top-level layers

```text
+-------------------------------------------------------------+
| Human / Codex / future research agent                       |
|  - reads docs                                               |
|  - creates or selects proposals                             |
+-------------------------------+-----------------------------+
                                |
                                v
+-------------------------------------------------------------+
| lab.cli                                                     |
|  bootstrap | preflight | campaign | run | night | report    |
|  inspect | replay | export-code-proposal | score | cleanup  |
+-------------------------------+-----------------------------+
                                |
                                v
+-------------------------------------------------------------+
| Stable lab infrastructure                                   |
|                                                             |
|  runner        ledger        scheduler      campaigns       |
|  worktrees     artifacts     archive        backends        |
|  crash class   reports       scoring        cleanup         |
+-------------------------------+-----------------------------+
                                |
                                v
+-------------------------------------------------------------+
| Mutable research surface                                    |
|                                                             |
|  research/dense_gpt/                                        |
|    defaults.py                                              |
|    train.py                                                 |
|    model.py                                                 |
|    optim.py                                                 |
|    search_space.py                                          |
|    mutation_rules.py                                        |
+-------------------------------+-----------------------------+
                                |
                                v
+-------------------------------------------------------------+
| Campaign assets                                             |
|                                                             |
|  manifests | tokenizer assets | pretokenized shards         |
|  packed blocks | eval splits | asset manifests              |
+-------------------------------------------------------------+
```

## Repo shape

The intended repo shape is:

```text
AGENTS.md
ARCHITECTURE.md
CODEX_GUARDRAILS.md
docs/
schemas/
sql/
templates/
tools/
reference_impl/
lab/
research/
campaigns/
tests/
artifacts/        (gitignored)
.worktrees/       (gitignored)
.lab.env          (local, not committed by default)
```

## Stable vs mutable boundary

### Stable lab infrastructure
Files under `lab/`, `schemas/`, and `sql/` are the durable operating system of the lab.
They should:
- have clear contracts
- use structured data
- be testable
- change slowly

### Mutable research surface
Files under `research/dense_gpt/` are where experimentation happens.
They may change more often, but they:
- must respect campaign contracts
- must emit structured summaries
- must remain hackable
- must not leak chaos into the lab layer

## Proposal model

A proposal has two independent dimensions.

### Proposal family
Research intent:
- baseline
- exploit
- ablation
- combine
- novel
- manual

### Proposal kind
Implementation mode:
- structured
- code_patch
- manual

The scheduler reasons about family.
The runner and export/import flow reason about kind.
Reports should show both.

## Proposal lanes

The lab supports two complementary proposal lanes.

### 1. Structured proposal lane
- no external coding agent required
- proposals are generated from `search_space.py`
- ideal for dense hyperparameter and schedule exploration
- best for overnight throughput

### 2. Code proposal lane
- exported as a worktree + task pack for Codex/Claude/etc.
- used for architecture or trainer changes that exceed structured config mutation
- result comes back as a local commit/patch and is then scored by the same lab runner

The scheduler arbitrates across both lanes.

## Core persistent objects

The lab persists these first-class objects:

- campaigns
- proposals
- experiments
- artifacts
- champions
- daily reports
- backend cache entries
- worktree records (if code proposals are enabled)

## Architectural invariants

These are hard invariants:

- runner decisions use structured data
- campaign manifests are explicit
- experiment ids are created before execution
- artifacts are append-only per experiment
- stable infrastructure and mutable research surface are separated
- mainline repo remains clean during proposal execution
- campaign comparability is never inferred implicitly
- proposal family and proposal kind remain separate
- raw logs do not drive promotion or scheduling

## Why SQLite

SQLite is the right choice here because it is:
- local
- zero service dependency
- durable
- inspectable
- easy to query
- sufficient for one-user, one-machine operation

Anything bigger is premature.

## Why worktrees

Worktrees provide:
- clean isolation
- reproducible patch provenance
- easier cleanup
- simpler replays
- less branch dirtiness

## Why reports over dashboards

The user wants an answer in the morning, not a platform to administrate.
Static Markdown or HTML reports are enough for v1 and likely better.

## What to read next

1. `CODEX_GUARDRAILS.md`
2. `docs/design-docs/index.md`
3. `docs/design-docs/file-by-file-blueprint.md`
4. `docs/design-docs/algorithmic-appendix.md`
