# The Remembering Scientist

Autoresearch Lab is built around a simple idea:

`A one-GPU research lab should get stronger when it can remember what it learned.`

This page summarizes the current showcase surface. The linked pilot notes are historical records from the first bounded A/B run, while the current repo now records first-class evidence and retrieval events in normal operation.

Same GPU. Same campaign. Same budget. The only intended difference was memory.

## What We Tested

We ran the lab twice on `base_2k`:

- `remembering`: started from a frozen historical notebook built from prior runs, proposals, archive state, and report output
- `amnesiac`: started with no historical memory and only same-session state

Both arms used:

- the same repo commit
- the same workstation and GPU
- the same campaign
- the same scheduler family
- the same confirm budget
- the same bounded launch policy

Because prep showed that short runs were finishing far earlier than their nominal wall-clock budgets, the official search arms used:

```bash
python -m lab.cli night --campaign base_2k --hours 4 --max-runs 12 --allow-confirm --seed-policy mixed
```

That gave us a fair, bounded pilot instead of an uncontrolled flood of tiny runs.

## Why This Matters

The goal was not to prove that memory always wins.

The goal was to see whether a remembering lab behaves differently in a way that matters:

- does it search more strategically?
- does it avoid wasting effort?
- does it leave a more coherent research trail?
- does its best idea hold up better once replayed?

## Prep Work That Changed The Interpretation

Two prep findings mattered a lot.

### 1. Baseline noise was large

Repeated scout-lane baseline runs varied a lot:

- `20.346421`
- `16.601252`
- `15.232932`

Observed range:

- `5.113489`

That meant single scout wins were not trustworthy enough to carry the showcase on their own. Confirm replays were mandatory.

Detailed note:

- [BASELINE_NOTE.md](showcase/the-remembering-scientist/02_baseline_noise/BASELINE_NOTE.md)

### 2. The remembering arm needed a real seed

The repo-default `base_2k` memory state was too thin, so we first built a non-official seed notebook and froze it.

That seed captured:

- 8 prior runs
- multiple proposal families
- at least one failure
- archive state
- a report bundle with concrete recommendations

Seed manifest:

- [MANIFEST.md](showcase/the-remembering-scientist/01_seed_snapshot/MANIFEST.md)

## What Happened

### Official remembering arm

- runs attempted: `12`
- successful: `12`
- promoted: `1`
- failed: `0`
- best raw candidate: `exp_20260310_001509+0000_b51db484`
- best raw metric: `10.771031`
- winning family/lane: `exploit` / `main`

Committed summary:

- [pilot outcome](showcase/the-remembering-scientist/PILOT_OUTCOME.md)

### Official amnesiac arm

- runs attempted: `12`
- successful: `11`
- promoted: `6`
- failed: `1`
- best raw candidate: `exp_20260310_001703+0000_30ecf78e`
- best raw metric: `8.653343`
- winning family/lane: `novel` / `scout`

Committed summary:

- [pilot outcome](showcase/the-remembering-scientist/PILOT_OUTCOME.md)

At first glance, the amnesiac arm looked stronger. It found a flashier raw winner and promoted more candidates in the search window.

That was exactly why the confirm stage mattered.

## Confirm And Replay Results

We replayed the best candidate from each arm at a bounded confirm budget and also ran a clean baseline replay.

| Run | Experiment | Metric |
| --- | --- | ---: |
| Clean baseline replay | `exp_20260310_001901+0000_662c675f` | `19.273767` |
| Remembering confirm | `exp_20260310_001836+0000_c53c1438` | `15.413058` |
| Amnesiac confirm | `exp_20260310_001849+0000_09783be0` | `16.634862` |
| Clean finalist replay | `exp_20260310_001931+0000_356ea92f` | `12.607273` |

The pilot's most important result is here:

- the amnesiac arm won the raw-search highlight reel
- the remembering arm produced the candidate that held up better under replay

Both confirmed finalists beat the clean baseline replay, but the remembering finalist stayed ahead after the flashy raw amnesiac win regressed.

## What We Learned

This pilot supports a careful version of the memory thesis:

`Memory improved stability more than it improved raw flashiness.`

The remembering arm looked narrower and more conservative during search. The amnesiac arm looked bolder and more explosive. But once we stopped rewarding single noisy highlights and replayed the best ideas, the remembering arm came out ahead.

That is a meaningful result for a research lab. It suggests the value of memory may be less about finding the wildest first hit and more about producing ideas that survive a second look.

## Caveats

This is a first public-facing draft, so the caveats matter.

### 1. This was a bounded pilot, not the full flagship

This was one short A/B pair with confirms, not the larger multi-pair showcase plan.

### 2. The eval path is still noisy

The baseline noise note and the confirm regressions both point to the same thing: raw leaderboard wins are not reliable enough by themselves.

### 3. The published pilot artifacts predate the strongest evidence fields

The current repo does log first-class evidence and retrieval events. This particular frozen pilot was run before the showcase materials were regenerated around those stronger fields, so some of the linked writeups still rely partly on seeded state and proposal trajectory when explaining memory effects.

### 4. This does not prove broad superiority

This pilot does **not** justify claims like:

- "Autoresearch Lab is universally better than forgetting"
- "Autoresearch Lab is already proven better than upstream in general"
- "The raw leaderboard alone is enough to judge the winner"

## Best Honest Claim Right Now

If I had to summarize the result in one line, it would be this:

`In a bounded one-GPU A/B pilot, the amnesiac lab found flashier raw winners, but the remembering lab produced the candidate that held up better once the best ideas were replayed.`

That is not the final flagship claim. It is the honest first signal that the flagship concept is worth continuing.

## Where The Full Version Would Go Next

The next stronger version of this showcase should add one or more of:

- a second official A/B pair
- stronger confirm coverage
- tighter evaluation behavior
- first-class memory citation logging
- a clearer repeated-dead-end metric

Until then, this pilot is best understood as a serious internal-to-public bridge:

- strong enough to show the lab's identity
- not yet strong enough to pretend the story is finished

## Related Notes

- [internal case study draft](showcase/the-remembering-scientist/CASE_STUDY_DRAFT.md)
- [pilot outcome](showcase/the-remembering-scientist/PILOT_OUTCOME.md)
- [protocol](showcase/the-remembering-scientist/00_protocol/PROTOCOL.md)
