# AGENTS.md

This repository is being evolved into **Autoresearch Lab**: a real single-GPU research lab built on top of Karpathy's minimal `autoresearch` concept.

## Mission

Build a local, CUDA-first research system that:

- keeps the core dense-model trainer hackable
- adds real experiment infrastructure around it
- supports both structured and code-level research loops
- is robust enough to run overnight on one workstation
- remains small enough that humans and agents can reason about it from the repo alone

## Product target in one sentence

**A single-GPU, dense-model, campaign-aware, artifact-rich research lab with a real runner, real memory, real scheduling, and real reporting.**

## Hard constraints

These are non-negotiable unless a phase doc explicitly changes them.

1. **Single GPU only**
   - no multi-GPU
   - no distributed training
   - no cluster assumptions

2. **CUDA first**
   - this repo is allowed to be narrow
   - portability is secondary to performance and clarity
   - backend selection should still degrade gracefully across NVIDIA single-GPU machines

3. **Dense-model first**
   - no MoE
   - no routers
   - no “gating program”
   - no giant architecture zoo

4. **Keep the research surface compact**
   - avoid turning the repo into a generic framework
   - use configuration and structured proposals where possible
   - isolate infrastructure from the mutable research surface

5. **In-repo knowledge is the system of record**
   - no hidden requirements in chat history
   - no undocumented assumptions
   - if a decision matters, encode it in repo docs or code

6. **Mechanical correctness beats prompt vibes**
   - runner must consume structured artifacts
   - no grep-driven control path
   - raw logs are for humans and debugging, not for primary control flow

## Proposal model

Proposals have **two axes**:

1. `family`
   - `baseline`
   - `exploit`
   - `ablation`
   - `combine`
   - `novel`
   - `manual`

2. `kind`
   - `structured`
   - `code_patch`
   - `manual`

Family is the research intent.
Kind is the implementation mode.

Do not collapse them into one field.

## Operating model

Separate the repo into two conceptual layers.

### A. Stable lab infrastructure
Stable code that should be legible, tested, and rarely changed once correct:

- CLI
- runner
- worktree manager
- ledger / SQLite
- artifacts
- campaigns
- scorers
- reports
- backend selection
- reliability and cleanup logic

### B. Mutable research surface
The part that is intentionally optimized for experimentation:

- dense model code
- train loop policy
- optimizer/search knobs
- structured search space
- optional code-level proposal packs

## Primary user

A solo researcher / tinkerer / engineer with one serious NVIDIA workstation who wants to:

- start runs before sleep
- wake up to meaningful results
- understand what happened
- extend the lab without drowning in infra

## What “better than the original” means

Not “more abstractions”.

It means:

- real runner and resume behavior
- real experiment database
- real archive and scheduler
- real multi-budget evaluation
- real campaign support
- real artifact hygiene
- real reports
- real failure recovery
- a better search engine
- richer dense-model search space
- while preserving the upstream repo's taste for compactness

## Non-goals

Do **not** build:

- distributed launchers
- Kubernetes / Ray / job queues
- hosted services
- fancy web apps before CLI/reporting is excellent
- a benchmark zoo
- a general-purpose AutoML framework
- a policy-gradient / RL experiment platform
- a dependency-heavy config framework
- a “gate everything” transformer lab

## Taste filters

Every design choice should pass these filters:

1. Will this materially improve research throughput, robustness, or legibility?
2. Is there a smaller implementation that achieves the same thing?
3. Can Codex understand the subsystem from repo-local docs and code?
4. Will a future agent be able to safely modify the research surface without breaking the lab layer?
5. Does this preserve the repo’s single-GPU personality?

## Build order

Implement in this order only:

1. Foundation and knowledge store
2. Runner + ledger + artifacts
3. Data pipeline + campaign assets
4. Evaluation ladder + promotion rules
5. Scheduler + archive + proposal system
6. Dense-model search surface
7. Campaigns + reporting
8. Reliability + cleanup + polish

## Required delivery discipline

For every phase:

- read the phase doc first
- implement the exact deliverables
- add or update tests
- run smoke checks
- update docs if reality changes
- update `docs/QUALITY_SCORE.md`
- update `docs/generated/resolved-ambiguities.md` when a contract or interpretation changes
- do not leave half-finished abstractions behind

## When blocked

If blocked by an underspecified detail:

1. choose the smallest implementation consistent with the architecture docs
2. check whether `reference_impl/` already resolves the ambiguity
3. document the decision
4. continue

Do not ask the human for clarification unless the repo or environment is genuinely unusable.

## Definition of done for the full project

The project is done when:

- the original baseline can be reproduced as a campaign
- the lab can run structured proposals without human babysitting
- code-level proposals can be exported and imported cleanly
- experiments are fully recorded in SQLite + artifacts
- overnight runs generate a morning report
- champions and near-misses are preserved in an archive
- crashes are classified and recoverable
- the repo remains compact and understandable
- the lab is actually useful on a single GPU workstation

## Read next

1. `ARCHITECTURE.md`
2. `CODEX_GUARDRAILS.md`
3. `docs/design-docs/index.md`
4. `docs/product-specs/index.md`
5. `docs/PLANS.md`
