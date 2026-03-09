# Research engine

## Research engine definition

The research engine is the combination of:
- proposal generation
- scheduling
- execution
- scoring
- promotion
- archiving
- reporting

It is the heart of the lab.

## Proposal families

Support at least these families:

1. `baseline`
   - establish reference points

2. `exploit`
   - small mutations around current champions

3. `ablation`
   - remove one suspected beneficial change to test causality

4. `combine`
   - merge orthogonal wins from different lineages

5. `novel`
   - intentionally explore under-covered regions of the search space

6. `manual`
   - human-authored or imported proposal

## Proposal kinds

Kinds are separate from families.

Kinds:
- `structured`
- `code_patch`
- `manual`

Examples:
- `family=combine`, `kind=structured`
- `family=novel`, `kind=code_patch`

## Proposal lane split

### Structured lane
Backed by:
- config overrides
- search space mutation rules
- schedule families
- architecture toggles that remain compile-friendly

### Code lane
Backed by:
- proposal pack export
- isolated worktree
- target files and acceptance criteria
- post-edit execution through the same runner

## Archive model

Maintain a small **elite archive** per campaign and budget lane.

Each archive entry should include:
- experiment id
- parent lineage
- key metrics
- config snapshot
- simplicity estimate
- novelty score
- disposition notes

The archive should preserve:
- top quality champions
- memory-efficient pareto points
- simplicity winners
- strategically useful near-misses

## Simplicity tax

Respect the upstream spirit that small wins are not worth ugly complexity.

Represent simplicity at least coarsely using:
- line delta
- number of files changed
- number of new special-case branches
- amount of backend-specific code added

Do not let this become a fake precision number.
A coarse bias is enough.

## Promotion ladder

Use at least three lanes:

- `scout`
- `main`
- `confirm`

### Scout
Cheap screening.
A poor candidate should die here.

### Main
Primary leaderboard lane.

### Confirm
Longer or replicated validation for candidates that look real.

## Recommendation engine

After every batch of runs, the engine should be able to answer:

- What won?
- What was surprisingly good but not promoted?
- Which crashes are worth fixing?
- Which ideas deserve ablation?
- Which orthogonal wins should be combined?
- Where is the search space under-explored?

## Code proposal pack

A code proposal pack should contain:
- proposal id
- title
- hypothesis
- parent run(s)
- target files
- constraints
- acceptance criteria
- current best comparators
- minimal relevant code context
- output contract

This gives Codex enough scaffolding to work without free-associating the product direction.

## Reference implementation note

Scheduler generation, queue ranking, archive maintenance, and promotion rules are intentionally made concrete in `reference_impl/`.
Use those semantics instead of inventing a weaker loop.
