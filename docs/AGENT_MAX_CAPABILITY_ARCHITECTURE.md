# Agent Max Capability Architecture

## Objective

Design Autoresearch Lab for increasingly capable research agents.

The repo should not be optimized for weak agents that need to be caged by default.
It should be optimized for strong agents that can:

- reason deeply
- generate hypotheses
- change code
- design new experiments
- run for hours
- improve their own search process

The right design is not:

- less structure
- more vibes
- fewer checks

The right design is:

**maximum freedom in proposing and executing research, paired with maximum hardness in measurement, lineage, and promotion.**

## Core Thesis

Do not constrain the agent's thinking.
Constrain the side effects.

That means:

- let the agent search broadly
- let the agent patch code
- let the agent create new proposal families
- let the agent revisit old failures
- let the agent run for hours

But keep these hard:

- comparability
- isolation
- provenance
- validation
- reproducibility
- promotion gates

## Desired End State

Autoresearch Lab should become:

- a local single-GPU research operating system
- with a strong agent as the primary operator
- where the agent can run long autonomous loops
- across both structured-search and code-change lanes
- while the lab keeps the evidence, scoring, and trust model honest

The ideal agent should be able to say:

`I ran for eight hours, explored several hypotheses, changed both configs and code, rejected my own weak ideas, validated the strongest candidates, and left a clean evidence trail.`

## First Principles

### 1. Agent-first, not CLI-first

The CLI should remain excellent for humans, but the architecture should assume the real long-run operator is an increasingly strong agent.

The repo should expose:

- readable state
- writable proposal surfaces
- explicit contracts
- safe isolated execution lanes
- machine-usable reports

### 2. Freedom in research, hardness in trust

The agent should be free to:

- pick or generate proposals
- alter hyperparameters
- alter trainer code
- alter the search space
- alter scheduler behavior
- add new experiment families
- create new validation strategies

The lab should remain hard about:

- what is comparable
- what counts as a result
- what counts as a validated result
- what can become a champion
- what is only a hypothesis

### 3. Code-change capability is not secondary forever

A strong future agent will outgrow a purely structured search space.

Therefore:

- structured proposals remain core for throughput
- code proposals must become equally serious for capability
- the system must support switching between those two lanes during one long autonomous run

### 4. Memory must become research memory

Memory should not stop at citation retrieval.

A strong agent needs durable memory for:

- what worked in which regime
- what failed and why
- which patches improved only raw metrics
- which changes survived confirm and audit
- which search branches repeatedly led nowhere
- which interventions were only hardware/runtime artifacts

### 5. Reports should teach the next run

The report is not just for the human in the morning.
It is also context for the next autonomous loop.

The most important outputs are:

- strongest surviving candidates
- strongest rejected candidates
- repeated dead ends
- unstable wins
- hypotheses worth revisiting
- hypotheses worth banning

## What Must Be Loosened

These are the areas where the current repo is still too conservative if the goal is maximum agent capability.

### 1. The structured lane is too dominant

Today the lab-native path is strongest when the agent stays inside the existing search surface.

That is good for stability, but limiting for a very strong agent.

The agent should increasingly be allowed to:

- propose new search dimensions
- patch mutation rules
- patch scoring heuristics
- patch trainer internals
- patch runtime strategy where scientifically valid

### 2. The code lane should become a first-class research lane

Today the code lane is real, but still feels like an extension path.

It should move toward:

- easier export/import loops
- stronger lineage and patch evaluation
- direct comparison of code-patch proposals against structured winners
- code proposals as normal overnight behavior, not just exceptional behavior

### 3. The autonomy loop should become explicit

The repo has `night`, but it still reads more like a human-launched batch path than a true autonomous agent loop.

The system should eventually support:

- a multi-hour agent session budget
- a proposal budget
- a code-patch budget
- periodic self-review checkpoints
- dynamic switching between structured and code lanes
- explicit stop conditions

### 4. The scheduler should become more self-improving

A strong agent should not only choose proposals.
It should improve the proposal system itself.

That means letting the agent:

- generate new proposal families
- revise family weights
- promote or demote exploration styles
- retire unhelpful branches
- fork new search regimes

## What Must Never Be Loosened

These are the invariants that protect the lab from becoming fake or self-delusional.

### 1. Comparability

Do not let the agent silently compare incomparable runs.

Campaign identity, eval split, budget, and purpose must stay explicit.

### 2. Promotion gates

Raw search wins must not become champions directly.

No matter how smart the agent becomes, this remains hard:

- raw result
- confirm
- audit
- champion

### 3. Isolation

Code experiments, workspaces, and run artifacts must remain isolated enough that one bad idea does not poison the rest of the lab state.

### 4. Durable lineage

Every important result must still answer:

- what proposal produced this
- what memory informed it
- what parent runs led to it
- what code changed
- what validation did it survive

### 5. Honest naming

Future agent capability must not be laundered through inflated wording.

If the agent is merely trying something, say so.
If a result is provisional, say so.
If a run failed the hypothesis, preserve that truth.

## Target Agent Loop

The ideal long-run loop is:

1. read current campaign state
2. inspect strongest surviving candidates
3. inspect strongest rejected candidates
4. inspect archive and repeated dead ends
5. form next hypotheses
6. choose whether each hypothesis belongs to:
   - structured lane
   - code lane
7. execute bounded experiments
8. validate promising candidates
9. ingest memory from results
10. revise the search policy itself
11. continue until time, budget, or confidence threshold ends the session

This should be treated as the real product loop for future agents.

## Architectural Requirements

### A. Machine-readable state everywhere

Agents get stronger when the system state is explicit and queryable.

Priorities:

- JSON summaries for all important decisions
- stable schema boundaries
- direct access to report JSON, validation JSON, and proposal context
- minimal dependence on human-only prose

### B. Code-lane trust parity

The code lane should flow through the same trust pipeline as the structured lane:

- same runner
- same scoring
- same validation
- same reports
- same lineage
- same memory ingestion

### C. Session-level autonomy

Add a session-level concept that groups:

- all proposals attempted
- lane switches
- code patches imported
- validation outcomes
- report checkpoints
- final session conclusion

This is the right unit for a strong agent's multi-hour work.

### D. Self-improving memory

Memory should evolve from:

- evidence citations

Toward:

- experiment policy memory
- failure-pattern memory
- patch-outcome memory
- validation-stability memory

## Capability Tiers For An Agent-First Lab

### Proven and core

- canonical campaign execution
- validation ladder
- ledger and lineage
- night sessions
- reports
- doctor and cleanup
- proof paths

### Strong next bets

- code lane as first-class overnight lane
- session-level autonomy
- policy memory
- agent-generated proposal families

### Promising but dangerous

- self-modifying scheduler logic without guardrails
- agent-authored promotion rules
- automatic loosening of comparability constraints
- autonomous claim-writing without verification

## Implementation Phases

## Phase 1: Agent-First Contracts

### Goal

Make the repo explicitly legible to a strong agent.

### Tasks

- keep `OPERATING_CONTRACT.md` and `RESEARCH_CONTRACT.md` current
- add an explicit agent-facing session contract
- ensure reports expose enough machine-readable state to drive the next loop

### Exit Criteria

- an agent can infer the canonical loop from repo docs alone
- an agent can tell core capabilities from secondary ones

## Phase 2: Code Lane Upgrade

### Goal

Make code proposals a true research lane, not a side path.

### Tasks

- simplify export/import flow
- improve patch lineage and comparison against structured winners
- add report views that compare code-lane and structured-lane outcomes directly

### Exit Criteria

- a multi-hour session can naturally mix structured and code proposals
- code results are not second-class in reports or validation

## Phase 3: Session-Level Autonomy

### Goal

Add a first-class session object for long autonomous agent work.

### Tasks

- create a session record and session manifest
- record session budgets, lane switches, and outcome summaries
- add periodic self-review checkpoints during `night`-like loops

### Exit Criteria

- the lab can explain one entire multi-hour autonomous session coherently

## Phase 4: Research Memory Upgrade

### Goal

Turn memory into a stronger research amplifier.

### Tasks

- track which ideas survived validation, not just which were cited
- track repeated bad patch patterns
- track regime-specific successes and failures
- expose memory usefulness in reports

### Exit Criteria

- memory helps choose better next experiments, not just decorate past ones

## Phase 5: Self-Improving Scheduler

### Goal

Let the agent improve the search policy without breaking trust.

### Tasks

- allow agent-authored proposal-family suggestions
- allow family-weight adjustments under explicit review
- keep hard constraints around comparability and promotion

### Exit Criteria

- the scheduler can improve over time without becoming opaque or self-deceptive

## Phase 6: Endurance Agent Mode

### Goal

Make the repo natively good for long-running strong agents.

### Tasks

- explicit long-session budgets
- bounded risky-code budgets
- periodic report checkpoints
- automatic stop conditions
- final session retrospective

### Exit Criteria

- a strong agent can work productively for hours without the lab dissolving into chaos

## Design Rule

When choosing between:

- more agent freedom
- more system trust

Prefer this answer:

**increase agent freedom in proposing and executing research, but never by weakening comparability, lineage, validation, or honest naming.**

That is the path to a lab that becomes more powerful as agents become more powerful.
