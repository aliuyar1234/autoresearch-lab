# The Remembering Scientist

This directory holds the reproducible showcase pipeline for the flagship memory-vs-amnesia case study.

The generated pilot notes in this directory are historical records from the first executed A/B pair. The current repo's evidence and retrieval lineage are stronger than some of those frozen writeups imply.

The core claim is simple:

`Same GPU. Same campaign. Same budget. The only difference was memory.`

## Workflow

1. Freeze a historical seed snapshot:
   `python showcase/the-remembering-scientist/freeze_memory_snapshot.py --campaign base_2k --source-db <db> --output-root showcase/the-remembering-scientist/01_seed_snapshot`
2. Run official A/B pairs with isolated roots:
   `python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --pairs 2 --hours 6`
3. Run confirm, audit, and clean replay passes:
   `python showcase/the-remembering-scientist/run_validations.py --campaign base_2k`
4. Render figure-input artifacts and the draft writeup:
   `python showcase/the-remembering-scientist/render_case_study.py --campaign base_2k`

## Output shape

- `pair_XX/remembering/` and `pair_XX/amnesiac/` contain isolated showcase arms.
- `compare.json` and `compare.md` summarize the official A/B pairs.
- `validations/` contains confirm, audit, and replay outputs.
- `figures/` contains reproducible figure-input JSON files.
- `CASE_STUDY_DRAFT.md` is generated from stored artifacts instead of hand-built notes.

## Fairness rules

- Same repo commit for both arms.
- Same campaign and runner logic.
- Same session budget and seed policy.
- Remembering arm gets a frozen historical snapshot.
- Amnesiac arm starts from empty historical state with the same schema.

## Important boundaries

- These scripts are showcase orchestration, not a second lab control plane.
- Real experiments still run through the normal lab runner and ledger.
- Figure files are data-first JSON inputs, not screenshot hacks.
