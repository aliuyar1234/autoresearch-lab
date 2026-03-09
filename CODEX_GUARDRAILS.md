# CODEX_GUARDRAILS.md

This file exists to prevent implementation drift.

Read it before changing code.

## The product in one sentence

Build a **compact, single-GPU, CUDA-first, dense-model research lab** around the original `autoresearch` trainer concept.

## The three axes that must stay separate

Do not blur these together:

1. **Campaign**
   - defines comparability, data, tokenizer, sequence length, budgets, metrics

2. **Proposal family**
   - `baseline`
   - `exploit`
   - `ablation`
   - `combine`
   - `novel`
   - `manual`

3. **Proposal implementation mode (`kind`)**
   - `structured`
   - `code_patch`
   - `manual`

If you collapse these into one concept, the scheduler, reports, and archive will become muddy.

## Stable lab layer vs mutable research layer

### Stable lab layer
This should be boring, explicit, and heavily tested.

Includes:
- CLI
- settings and path resolution
- runner
- ledger
- artifacts
- campaign loading and verification
- backend selection
- reports
- cleanup and resume
- schema validation

### Mutable research layer
This should be hackable and safe to iterate on.

Includes:
- dense model config surface
- optimizer groups
- training schedules
- architecture toggles
- mutation rules
- optional code proposals that alter the dense trainer

Do not let the mutable layer leak chaos into the stable layer.

## What Codex is likely to get wrong if not constrained

### 1. It may generalize into a framework
Do not build:
- plugin registries
- dynamic import systems for everything
- service abstractions for local code
- general-purpose experiment-tracking infrastructure

### 2. It may underspecify the scheduler
Do not implement the scheduler as:
- random mutation
- weighted-score soup
- “pick best metric delta” only

The scheduler must understand:
- proposal family
- lane
- archive state
- recent crashes
- novelty coverage
- campaign boundaries

Use `reference_impl/scheduler_policy.py`.

### 3. It may keep packing online
Do not leave tokenization and best-fit packing in the hot training path for campaign builds that are supposed to be offline.

Use `reference_impl/offline_packing.py` and the campaign asset model.

### 4. It may use raw logs as agent input
The lab must consume structured JSON summaries.
Raw logs are debugging artifacts, not the control plane.

### 5. It may over-index on the GPU and make the default model bloated
The workstation has large VRAM.
That does **not** mean “make the model huge by default.”
The point is:
- bigger device batch
- better confirm lanes
- 4k campaign room
- lower accumulation overhead
- higher experiment throughput

### 6. It may prematurely delete the baseline path
Do not remove the original top-level path until `base_2k` parity and regression checks are credible.

## Hard design choices already made

These are resolved.
Do not reopen them casually.

1. SQLite is the durable store.
2. CLI is the primary UX.
3. Markdown is the canonical report format.
4. Proposals are structured JSON.
5. Campaigns are committed manifests plus generated assets.
6. The runner writes manifests before launch.
7. The runner checkpoints before expensive final evaluation when configured.
8. Proposal intent (`family`) and implementation mode (`kind`) are separate.
9. Promotion is rule-based, not score-soup.
10. Dense-model search stays first-class; no MoE or router track.

## Allowed complexity

Complexity is allowed only when it buys one of these:

- materially more overnight throughput
- materially better reliability
- materially better auditability
- materially better research surface coverage
- materially better morning reports

If it does not buy one of those, remove it.

## File ownership rules

### Codex may frequently edit
- `research/dense_gpt/**`
- campaign builders
- scheduler mutation rules
- report summarization heuristics

### Codex should edit carefully
- `lab/runner/**`
- `lab/ledger/**`
- `lab/backends/**`
- `schemas/**`
- `sql/**`

### Codex should not casually edit after stabilized
- root architecture docs
- campaign comparability semantics
- report JSON contracts

## When to use the reference implementations

Use `reference_impl/` whenever the spec refers to a novel subsystem:

- scheduler policy
- promotion decisions
- archive maintenance
- backend selection
- crash classification
- offline packing
- report recommendation heuristics
- config fingerprinting
- campaign split rules

Those files are not decorative.
They are there to reduce drift.

## Review checklist for every nontrivial change

Before finalizing a change, ask:

1. Does it preserve campaign-local comparability?
2. Does it keep the control plane structured?
3. Does it avoid broadening scope into a framework?
4. Does it preserve or improve hackability?
5. Does it create more work for future cleanup than it is worth?
6. Does it violate any non-goal or hard constraint?
7. Did the docs and tests move with the code?

If any answer is bad, revise the change.
