# Base 2k Baseline Noise Note

Status: measured in isolated non-official workspace

Workspace:

- `showcase/the-remembering-scientist/workspaces/baseline_noise`

Campaign:

- `base_2k`

Configuration fingerprint:

- `a34bab1f139f`

Lane:

- `scout`

Budget:

- `90` seconds nominal

Important runtime note:

- these runs did not come close to spending the full nominal wall-clock budget because the trainer hit its step cap early
- first-run cold compile overhead was materially larger than subsequent replays

## Runs

1. `exp_20260309_235522+0000_afe9cd99`
   - seed: `42`
   - primary metric: `20.346421`
   - total seconds: `13.166696`

2. `exp_20260309_235546+0000_ff25c41f`
   - seed: `314`
   - primary metric: `16.601252`
   - total seconds: `4.395395`

3. `exp_20260309_235618+0000_12cca773`
   - seed: `2718`
   - primary metric: `15.232932`
   - total seconds: `4.386853`

## Simple Summary

- observed min: `15.232932`
- observed max: `20.346421`
- observed range: `5.113489`
- observed mean: `17.393535`

## Interpretation

This observed scout-lane variation is enormous relative to campaign thresholds:

- `scout_to_main_min_delta = 0.0004`
- `main_to_confirm_min_delta = 0.0003`
- `champion_min_delta = 0.0002`

Implication:

- single scout outcomes are not reliable enough to support the showcase claim by themselves
- confirm replays are mandatory
- the bounded pilot must be framed around confirmed finalists and research-trail coherence, not raw scout wins
- if later evidence shows this variance is systematic rather than just seed-sensitive, the pilot may need a tighter eval protocol before publication

## Practical Rule For The Pilot

Do not use single-scout metric deltas as the main evidence for "remembering beats amnesiac."

Use scout runs only as proposal-search behavior.
Use confirm replays and clean replays as the primary metric evidence.
