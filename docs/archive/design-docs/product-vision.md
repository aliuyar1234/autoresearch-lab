# Product vision

## Current baseline

The upstream repo is a brilliant minimal idea:
- fixed `prepare.py`
- mutable `train.py`
- human-authored `program.md`
- one 5-minute training budget
- one validation metric
- keep or discard commits based on `val_bpb`

That is the seed, not the finished lab.

## End product vision

The final product should behave like this:

1. The user initializes a campaign.
2. The lab verifies assets, backend, and machine state.
3. The scheduler creates structured proposals and optionally code proposal packs.
4. Runs execute in controlled worktrees with full artifacts.
5. The ledger records every proposal and experiment.
6. Candidates get promoted from scout to main to confirm.
7. Champions and near-misses are archived.
8. A morning report summarizes:
   - what won
   - what failed
   - what changed
   - what to try next
   - what to ignore
9. The user can replay, inspect, or extend any result.

## Why this is meaningfully better

The original is a local hill climber with memory written into git history and a TSV.
The upgraded product is a real lab because it has:
- explicit campaigns
- explicit budgets
- explicit archive
- explicit run manifests
- explicit proposal types
- explicit crash handling
- explicit reporting
- explicit quality guardrails

## What this should impress people with

Not novelty theater.

It should impress through:
- taste,
- leverage,
- compactness,
- run quality,
- and the feeling that one GPU can sustain a disciplined research loop.

## V1 launch bar

V1 is achieved when the lab can:

- reproduce the upstream baseline as `base_2k`
- run a meaningful overnight structured search
- export code-level proposal packs for bigger ideas
- recover cleanly from common failures
- produce a genuinely useful morning report
- and remain small enough that a new engineer can understand the architecture from the repo docs
