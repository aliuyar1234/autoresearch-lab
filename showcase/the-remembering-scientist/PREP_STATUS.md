# Pilot Prep Status

Status: official bounded pilot executed

This file records the current prep state for the bounded 12-hour pilot.

## Completed Checks

- repo bootstrap in `.venv`: passed
- `doctor --json`: passed cleanly
- `campaign list --json`: shows `base_2k`, `stories_2k`, `long_4k`
- `preflight --campaign base_2k --benchmark-backends --json`: passed cleanly
- `campaign verify --campaign base_2k --json`: passed cleanly
- isolated `baseline_noise` workspace: bootstrapped and preflight-clean
- isolated `remembering` workspace: bootstrapped and preflight-clean
- isolated `amnesiac` workspace: bootstrapped and preflight-clean

## Machine Verification Notes

- device profile: `rtx_pro_6000_96gb`
- GPU detected: NVIDIA RTX PRO 6000 Blackwell Workstation Edition
- selected backend: `sdpa`
- `kernels` backend currently unavailable in benchmark path
- `flex_attention` benchmark harness not wired
- no preflight warnings

## Campaign Decision Notes

Primary campaign:

- `base_2k`

Why:

- verified and ready now
- strongest parity-oriented campaign
- stable and closest to the upstream spirit

Secondary audit candidate:

- `stories_2k`

Current blocker:

- build fails because the required raw TinyStories text corpus is not staged under `artifacts/cache/raw/tinystories-gpt4-clean`

Pilot decision:

- do not require external sibling audit for the bounded 12h pilot
- defer sibling-campaign audit until `stories_2k` source data is staged

## Instrumentation And Fairness Gaps

Current gaps discovered during prep:

1. No first-class retrieval log
   - there is no dedicated retrieval artifact with query text, ranked memory IDs, or attached memory items

2. No schema-level `cited_memory_ids`
   - `schemas/proposal.schema.json` does not currently record explicit memory citations

3. No schema-level `cited_failure_ids`
   - failed-family references are not explicitly captured as structured fields

4. No current historical seed
   - the main repo ledger currently reports `0` `base_2k` experiments
   - there is no meaningful frozen historical snapshot yet

5. `stories_2k` is not build-ready out of the box on this machine
   - requires local source staging

## Practical Consequence

The pilot can still be prepared honestly, but it cannot claim a rich retrieval-backed historical-memory story until a pre-pilot seed snapshot is created.

## Seed Snapshot Update

The remembering seed is now available from the non-official `seed_builder` session and has been cloned into the remembering workspace.

What it contains:

- 8 non-official runs
- baseline, novel, and combine families
- one failed run
- discarded and promoted outcomes
- archive state
- a report bundle with recommendations

Seed sources:

- `showcase/the-remembering-scientist/workspaces/seed_builder`
- `showcase/the-remembering-scientist/01_seed_snapshot`

## Baseline Noise Finding

Non-official scout-lane baseline measurement on `base_2k` produced a very large spread:

- `20.346421`
- `16.601252`
- `15.232932`

Observed range:

- `5.113489`

Important implication:

- scout-lane outcomes are far noisier than the configured promotion thresholds
- any publication-quality pilot must treat scout runs as search behavior, not final evidence
- confirm replays are mandatory

Detailed note:

- `showcase/the-remembering-scientist/02_baseline_noise/BASELINE_NOTE.md`

## Official Launch Risk

Prep revealed a second major issue:

- actual run wall-clock is far shorter than the nominal campaign budget
- each run retains a checkpoint artifact
- a literal uncapped 4-hour official session would likely create an excessive number of runs and large artifact growth

Practical implication:

- the official pilot must use an explicit run cap instead of relying on nominal hours alone
- the adopted launch policy is `--hours 4 --max-runs 12` per official arm
- confirm and replay steps stay as bounded single-run checks

## Next Required Prep Steps

1. Assemble the comparison figures from the official arm reports and confirm summaries
2. Write the go / no-go note for the full flagship showcase
3. Decide whether to strengthen the eval protocol before any public-facing claim

## Official Pilot Execution Summary

Official search policy used:

- `remembering`: `night --campaign base_2k --hours 4 --max-runs 12 --allow-confirm --seed-policy mixed`
- `amnesiac`: `night --campaign base_2k --hours 4 --max-runs 12 --allow-confirm --seed-policy mixed`

Official arm outcomes:

- remembering: `12` runs, `12` successful, `1` promoted, best raw metric `10.771031`
- amnesiac: `12` runs, `11` successful, `1` failed, `6` promoted, best raw metric `8.653343`

Confirm and clean replay outcomes:

- remembering confirm replay of `exp_20260310_001509+0000_b51db484` -> `15.413058`
- amnesiac confirm replay of `exp_20260310_001703+0000_30ecf78e` -> `16.634862`
- clean baseline replay -> `19.273767`
- clean finalist replay of the remembering winner -> `12.607273`

Immediate interpretation:

- the amnesiac arm produced the most dramatic raw scout result
- that raw advantage did not survive confirm replay
- the remembering arm also regressed on confirm, but less severely
- on the bounded pilot's replay evidence, the remembering finalist remained stronger than the amnesiac finalist
- the current eval path is still noisy enough that a stronger public claim would need either more confirms or a tighter eval protocol
