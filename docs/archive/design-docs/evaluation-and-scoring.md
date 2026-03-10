# Evaluation and scoring

## Core principle

The lab should still optimize a clear primary metric, but must stop behaving like a blind one-number loop.

## Primary metric

For `base_2k`, the primary metric remains validation BPB.

This preserves upstream intent:
- vocab-size independence
- direct comparability within the campaign
- fixed-budget fairness

## Evaluation lanes

### Search validation
Cheap and frequent.
Used for proposal triage.

### Audit validation
Slightly stronger or alternate holdout.
Used before declaring a candidate meaningfully better.

### Locked validation / confirm
Touched sparingly.
Used only for promoted candidates.

## Budget lanes

### Scout
Fast filter.
Example default: 90 seconds.

### Main
Comparable lane.
Default target for parity with upstream concepts.
Example default: 300 seconds.

### Confirm
Longer or replicated validation.
Example default: 1200 seconds or second-seed confirmation.

## Promotion rules

A candidate should not promote just because it is the smallest floating-point improvement.

At minimum promotion should consider:
- absolute metric delta
- lane-specific threshold
- whether the candidate is a complexity regression
- whether the result replicated or survived audit

## Complexity-aware decision policy

Use a lexicographic / rule-based policy, not a mushy weighted average:

1. valid terminal run?
2. campaign + lane comparable?
3. better primary metric beyond threshold?
4. if roughly tied, prefer simpler / cheaper / lower-VRAM design
5. if still tied, prefer novel coverage or easier-to-extend variant

## Secondary metrics

Track these for context:
- peak VRAM
- compile time
- train time
- eval time
- tokens/sec
- steady-state MFU
- total tokens
- parameter count

Do not let them replace the primary metric.
Do use them for:
- pareto archiving
- morning report commentary
- backend tuning

## Replication policy

Use a light replication policy:
- fixed seed in scout/main for speed and comparability
- second seed or longer confirm only for promising candidates

This is enough for a local lab without exploding cost.
