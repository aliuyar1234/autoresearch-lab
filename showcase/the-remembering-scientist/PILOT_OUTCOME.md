# The Remembering Scientist - Bounded Pilot Outcome

Status: executed, not yet polished for public release

## Pilot Scope Actually Run

This pilot used the frozen `base_2k` protocol and the explicit bounded launch policy adopted during prep:

- official `remembering` search arm: `--hours 4 --max-runs 12`
- official `amnesiac` search arm: `--hours 4 --max-runs 12`
- one confirm replay for each arm at `--time-budget-seconds 300`
- one clean baseline replay at `--time-budget-seconds 300`
- one clean finalist replay for the stronger confirmed arm at `--time-budget-seconds 300`

The actual wall-clock consumed was far lower than the nominal envelope because runs hit internal step limits early.

## Official Arm Results

### Remembering

- workspace: `showcase/the-remembering-scientist/workspaces/remembering`
- report: `artifacts/reports/2026-03-10/base_2k/report.md`
- total runs attempted: `12`
- total successful runs: `12`
- total promoted runs: `1`
- total failed runs: `0`
- best raw candidate: `exp_20260310_001509+0000_b51db484`
- best raw metric: `10.771031`
- best raw family / lane: `exploit` / `main`

### Amnesiac

- workspace: `showcase/the-remembering-scientist/workspaces/amnesiac`
- report: `artifacts/reports/2026-03-10/base_2k/report.md`
- total runs attempted: `12`
- total successful runs: `11`
- total promoted runs: `6`
- total failed runs: `1`
- best raw candidate: `exp_20260310_001703+0000_30ecf78e`
- best raw metric: `8.653343`
- best raw family / lane: `novel` / `scout`

## Confirm And Replay Results

### Clean baseline replay

- source experiment: `exp_20260309_235522+0000_afe9cd99`
- replay experiment: `exp_20260310_001901+0000_662c675f`
- primary metric: `19.273767`

### Remembering confirm

- source experiment: `exp_20260310_001509+0000_b51db484`
- replay experiment: `exp_20260310_001836+0000_c53c1438`
- primary metric: `15.413058`

### Amnesiac confirm

- source experiment: `exp_20260310_001703+0000_30ecf78e`
- replay experiment: `exp_20260310_001849+0000_09783be0`
- primary metric: `16.634862`

### Clean finalist replay

- source experiment: `exp_20260310_001509+0000_b51db484`
- replay experiment: `exp_20260310_001931+0000_356ea92f`
- primary metric: `12.607273`

## Pilot Read

What the bounded pilot did show:

- the remembering arm searched in a narrower, more conservative way
- the amnesiac arm produced more dramatic raw wins and more promoted candidates
- the raw best amnesiac result did not survive confirm replay
- the remembering arm also regressed on confirm, but it remained ahead of the amnesiac confirm
- both confirmed finalists beat the clean baseline replay

What the bounded pilot did not show strongly enough yet:

- a stable raw-to-confirm pipeline
- a rich retrieval-citation story inside this frozen pilot artifact set; the current repo now records stronger evidence and retrieval lineage than this run captured
- a robust enough metric lane to support a loud flagship claim from one short pair alone

## Recommendation

Recommendation: treat this as a successful internal pilot but not yet as the finished public flagship.

Why:

- the pilot was useful and directionally supportive of the memory story
- the confirm stage mattered and changed the apparent winner
- the current eval variance is still high enough that a public-facing flagship should add either:
  - a tighter eval protocol, or
  - more confirm repetitions, or
  - a second official pair

## Best Current Public Claim

If this pilot were summarized publicly right now, the honest claim would be:

`In a bounded one-GPU A/B pilot, the amnesiac lab found flashier raw winners, but the remembering lab held up better once the best candidates were replayed.`

Do not yet claim:

- that remembering is universally better
- that the pilot proves broad superiority over upstream
- that the current raw leaderboard alone is trustworthy

## Next Recommended Step

Before writing the full public showcase:

1. keep this pilot as evidence that the concept is worth continuing
2. tighten the eval story or add more confirms
3. then run a stronger pair or a second pair for the flagship writeup
