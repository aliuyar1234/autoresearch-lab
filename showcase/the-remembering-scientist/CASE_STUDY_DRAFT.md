# The Remembering Scientist

## Internal Case Study Draft

Status: internal draft for review, not ready for external publication

## Executive Summary

We ran a bounded A/B pilot of Autoresearch Lab on a single GPU to test a simple idea:

`Does a lab with frozen historical memory behave better than an otherwise identical lab that starts with amnesia?`

The answer from this first pilot is:

- directionally yes
- loudly and conclusively no

The amnesiac arm found the flashiest raw winner during search. The remembering arm held up better once the best candidates were replayed under confirm conditions. That is a meaningful signal in favor of the memory thesis, but not yet strong enough to publish as the finished flagship story.

The right internal read is:

- the showcase concept is viable
- the current evaluation path is still noisy
- the next iteration should strengthen confirmation before we make a public memory-first claim

## Why We Ran This

Autoresearch Lab is meant to be more than an experiment runner. The project’s core ambition is to behave like a small one-GPU research lab with:

- persistent memory
- a proposal system
- archive and champion tracking
- unattended night sessions
- morning reports

The flagship showcase concept for that identity is `The Remembering Scientist`:

`Same GPU. Same campaign. Same budget. The only difference was memory.`

This bounded pilot was designed to test whether that story survives first contact with real runs.

## Protocol In Brief

The pilot used the frozen protocol in [PROTOCOL.md](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/00_protocol/PROTOCOL.md).

Common factors across both arms:

- same repo commit
- same machine and GPU
- same `base_2k` primary campaign
- same scheduler family and runner behavior
- same official search cap
- same confirm budget

The only intended difference:

- `remembering` had access to a frozen historical notebook
- `amnesiac` had no historical memory, only same-session state

Because prep showed that runs finish far earlier than nominal wall-clock budgets, the official bounded launch policy was tightened to:

- `night --campaign base_2k --hours 4 --max-runs 12`

for each official search arm.

## Prep Work That Mattered

Before the official A/B, we did three pieces of prep that materially affected interpretation.

### 1. Baseline noise check

In the isolated baseline workspace, repeated scout-lane baseline runs varied a lot:

- `20.346421`
- `16.601252`
- `15.232932`

Observed range:

- `5.113489`

This was much larger than the configured promotion thresholds and immediately told us not to trust single scout wins as headline evidence. That note is preserved in [BASELINE_NOTE.md](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/02_baseline_noise/BASELINE_NOTE.md).

### 2. Frozen remembering seed

The repo-default `base_2k` state was too empty to support a real memory-vs-amnesia comparison, so we first ran a non-official seed-building session and froze its outputs into [MANIFEST.md](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/01_seed_snapshot/MANIFEST.md).

That seed contributed:

- 8 prior runs
- multiple proposal families
- at least one failure
- archive state
- a report bundle with concrete recommendations

### 3. Honest audit simplification

The original larger showcase plan wanted a sibling audit campaign. For this bounded pilot we kept the comparison on `base_2k` only, because `stories_2k` is not turnkey on this machine without additional raw source staging. That simplification was intentional and should stay explicit in any later writeup.

## What We Ran

### Remembering arm

- workspace: `showcase/the-remembering-scientist/workspaces/remembering`
- command shape: `night --campaign base_2k --hours 4 --max-runs 12 --allow-confirm --seed-policy mixed`
- result:
  - 12 runs attempted
  - 12 successful
  - 1 promoted
  - 0 failed

Best raw result:

- experiment: `exp_20260310_001509+0000_b51db484`
- family / lane: `exploit` / `main`
- metric: `10.771031`

Morning report:

- [remembering report](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/workspaces/remembering/artifacts/reports/2026-03-10/base_2k/report.md)

### Amnesiac arm

- workspace: `showcase/the-remembering-scientist/workspaces/amnesiac`
- command shape: `night --campaign base_2k --hours 4 --max-runs 12 --allow-confirm --seed-policy mixed`
- result:
  - 12 runs attempted
  - 11 successful
  - 6 promoted
  - 1 failed

Best raw result:

- experiment: `exp_20260310_001703+0000_30ecf78e`
- family / lane: `novel` / `scout`
- metric: `8.653343`

Morning report:

- [amnesiac report](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/workspaces/amnesiac/artifacts/reports/2026-03-10/base_2k/report.md)

## What The Search Looked Like

The two arms behaved differently in a way that is already narratively useful.

The remembering arm:

- searched more narrowly
- concentrated on exploit-family follow-ups
- produced only one promoted winner in the official window
- looked more conservative and less dramatic

The amnesiac arm:

- produced more promoted runs quickly
- explored more broadly
- surfaced a much stronger-looking raw scout result
- also took on more failure and more raw variance

That behavioral split is visible in the morning reports even before confirms:

- remembering looks like a lab extending an existing line of thought
- amnesiac looks like a lab flailing wider and occasionally hitting something exciting

That is a useful difference. It is also exactly the kind of difference that can fool us if we stop at raw leaderboard numbers.

## Confirm And Replay Results

To avoid overclaiming from noisy search outcomes, we replayed the best candidate from each arm at a bounded confirm budget.

### Clean baseline replay

- source: `exp_20260309_235522+0000_afe9cd99`
- replay: `exp_20260310_001901+0000_662c675f`
- metric: `19.273767`

### Remembering confirm

- source: `exp_20260310_001509+0000_b51db484`
- replay: `exp_20260310_001836+0000_c53c1438`
- metric: `15.413058`

### Amnesiac confirm

- source: `exp_20260310_001703+0000_30ecf78e`
- replay: `exp_20260310_001849+0000_09783be0`
- metric: `16.634862`

### Clean finalist replay

- source: `exp_20260310_001509+0000_b51db484`
- replay: `exp_20260310_001931+0000_356ea92f`
- metric: `12.607273`

## Interpretation

This pilot produced a very specific and useful outcome:

- the amnesiac arm won the raw-search highlight reel
- the remembering arm won the more believable replay outcome

That matters because the baseline-noise prep already told us scout-lane outcomes are unstable. The confirm stage validated that warning. The most dramatic raw result of the pilot did not survive replay.

This is the strongest internal takeaway:

`Memory did not produce the loudest first impression, but it did produce the candidate that held up better under replay.`

That is not yet a finished public headline. It is, however, exactly the sort of internal evidence that says the showcase concept is worth continuing.

## Did The Pilot Meet Its Success Rules?

Against [SUCCESS_RULES.md](E:/autoresearch_lab_codex_spec_pack_patched_v1_1/autoresearch_repo/showcase/the-remembering-scientist/00_protocol/SUCCESS_RULES.md):

### What clearly passed

- baseline noise was measured and documented
- both official arms completed under the bounded policy
- the artifact minimum was produced:
  - baseline noise note
  - morning reports for both arms
  - confirm outputs
  - clean baseline replay
  - clean finalist replay

### What partially passed

- `better confirmed primary result`
  - yes, remembering beat amnesiac on confirm
- `faster time to first promoted keep`
  - no, amnesiac clearly moved faster in raw search
- `lower repeated-dead-end rate`
  - not strongly measurable yet with current schema/logging
- `one believable memory-driven example`
  - only weakly inferable from seeded trajectory, not strongly demonstrated
- `visibly more coherent morning report`
  - directionally yes, but still more of a qualitative impression than a formal result

### Bottom line

The pilot counts as a successful internal checkpoint, but not as a completed flagship validation.

## What This Pilot Did Not Yet Prove

We should be explicit here, because this is where projects often start lying to themselves.

This pilot did not prove:

- that remembering is universally better than forgetting
- that Autoresearch Lab is broadly better than Karpathy’s original setup
- that the current raw leaderboard is trustworthy on its own
- that we already have a strong enough memory-in-action artifact for public release

Two gaps matter most.

### 1. Eval noise is still too high

The baseline noise note and the confirm regressions both point to the same issue: the current search metric is noisy enough that raw highlights are not dependable.

### 2. This pilot predates the strongest evidence fields

The pilot runbook wanted memory to be visible. The current repo now records first-class evidence and retrieval events, but this frozen pilot artifact set predates the stronger showcase wiring. That means these writeups still infer some memory effects from trajectory and seeded state instead of showing the cleanest possible retrieval-to-proposal-to-result chain.

## Recommended Internal Read

This pilot should raise our confidence in the showcase concept, but not tempt us into publishing too early.

Best internal summary sentence:

`The pilot suggests that memory improves research stability more than it improves raw flashiness.`

That is a strong product insight. It also fits the system we built: archive, champion tracking, and night reports should be about compounding judgment, not just generating dramatic one-off winners.

## Recommendation For The Next Iteration

Do not discard this pilot. It did useful work.

The right next step is:

1. keep this pilot as the internal proof that the concept is real
2. strengthen confirm and replay rigor before public framing
3. run a second official pair or a slightly stronger confirm protocol
4. only then write the polished flagship showcase

Most important improvements before a public version:

- tighter confirm story
- stronger repeated-dead-end evidence
- better memory traceability

## Best Safe Claim Right Now

If we needed to summarize this pilot for internal stakeholders in one line, it would be:

`In a bounded one-GPU A/B pilot, the amnesiac lab found flashier raw winners, but the remembering lab produced the candidate that held up better once we replayed the best ideas.`

That claim is honest, useful, and strong enough to justify a better second pass.
