# The Remembering Scientist

This directory is the reproducible operator path for the memory-vs-amnesia showcase.

It is not a second control plane. The scripts here orchestrate isolated lab workspaces and then summarize their outputs.
It is also not the main identity of the repo; it is the secondary public proof path layered on top of the lab.

## Terminology

- `confirm`: promotion review on `search_val`
- `audit`: robustness review on `audit_val`
- `replay`: locked publication check on `locked_val`

Those meanings should stay stable across scripts, reports, and docs.

## Official Workflow

1. Freeze the seed snapshot used by the remembering arm:

```bash
python showcase/the-remembering-scientist/freeze_memory_snapshot.py --campaign base_2k --source-db <workspace>/lab.sqlite3 --output-root showcase/the-remembering-scientist/01_seed_snapshot
```

2. Run one or more official A/B pairs:

```bash
python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm
```

3. Run confirm, audit, and locked replay artifacts:

```bash
python showcase/the-remembering-scientist/run_validations.py --campaign base_2k --output-root showcase/the-remembering-scientist
```

4. Render figure inputs plus the generated case-study draft:

```bash
python showcase/the-remembering-scientist/render_case_study.py --campaign base_2k --output-root showcase/the-remembering-scientist
```

5. Verify the generated bundle:

```bash
python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json
```

This checks that cited rows still exist in SQLite, referenced files still exist on disk, and replay / validation claims are still backed by the stored bundle.

## Output Shape

- `compare.json` and `compare.md`: official A/B pair summaries
- `candidate_summary.json`: compact candidate summary across pairs
- `validations/confirm_comparison.json`: confirm review artifacts
- `validations/audit_comparison.json`: audit review artifacts
- `validations/clean_replays.json`: locked replay artifacts
- `validations/validation_summary.json`: consolidated validation, lineage, and citation summary
- `figures/*.json`: reproducible figure inputs
- `CASE_STUDY_DRAFT.md`: generated writeup draft

Each pair also keeps isolated workspaces:

- `pair_XX/remembering/`
- `pair_XX/amnesiac/`

Each arm workspace contains its own `lab.sqlite3` plus report artifacts under `artifacts/reports/`.

## Evidence And Lineage

The current repo's showcase path is evidence-traced:

- candidate proposals carry `retrieval_event_id` and `evidence[]`
- validation summary artifacts expose `memory_citation_examples`
- candidate lineage is exported via `candidate_lineage_references`
- repeated-dead-end metrics are included in both reports and showcase validation summaries

Use these files when checking the public claim:

1. `compare.json`
2. `validations/validation_summary.json`
3. the finalist arm reports
4. the finalist proposals

Run `tools/verify_showcase_bundle.py` before publishing or citing the bundle as evidence.

Current interpretation discipline:

- higher memory citation coverage does not automatically mean better final outcomes
- raw winners, confirmed winners, and audited winners can diverge
- a healthy showcase is allowed to produce mixed or hypothesis-negative results

## What Is Historical

Older pilot notes and templates live under `showcase/the-remembering-scientist/archive/`. Prefer the generated JSON artifacts and current scripts when deciding what the repo actually does now.
