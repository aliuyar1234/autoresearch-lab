# The Remembering Scientist

This repo's public showcase is a bounded A/B test.

It is a secondary proof path on top of the lab, not the identity of the repo:

`Same GPU. Same campaign. Same budget. The only intended difference is memory.`

The showcase compares two isolated workspaces on `base_2k`:

- `remembering`: starts from a frozen historical snapshot
- `amnesiac`: starts from the same schema with no historical memory

The current repo behavior is stricter than some older pilot writeups under `showcase/the-remembering-scientist/`. Search winners are no longer treated as trustworthy just because they topped a raw leaderboard.

## Trust Model

- `provisional`: a search result exists, but it has not survived confirm or audit review yet
- `confirmed`: the candidate survived confirm review against a comparable baseline
- `audited`: the candidate was measured on `audit_val` as a robustness check
- `regressed`: the candidate completed, but failed review or did not hold up as a keep-worthy result
- `invalid`: the run did not finish with a usable metric

Operationally:

- `confirm` is the promotion gate for strong candidates
- `audit` is a robustness read on `audit_val`, not the main headline metric
- `replay` is a locked publication check on `locked_val`, outside the normal promotion path

## Official Proof Path

These are the repo-native commands. They do not require historical planning material.

1. Freeze the historical seed snapshot:

```bash
python showcase/the-remembering-scientist/freeze_memory_snapshot.py --campaign base_2k --source-db <workspace>/lab.sqlite3 --output-root showcase/the-remembering-scientist/01_seed_snapshot
```

2. Run the official remembering vs amnesiac arms:

```bash
python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm
```

3. Run confirm, audit, and locked replay validation artifacts:

```bash
python showcase/the-remembering-scientist/run_validations.py --campaign base_2k --output-root showcase/the-remembering-scientist
```

4. Render figure inputs and the generated case-study draft:

```bash
python showcase/the-remembering-scientist/render_case_study.py --campaign base_2k --output-root showcase/the-remembering-scientist
```

5. Verify that the published bundle still matches stored rows and artifact paths:

```bash
python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json
```

The verifier checks that cited proposal, experiment, retrieval, memory, and validation-review ids still exist in SQLite, that referenced files still exist on disk, and that confirm/replay claims are backed by ledger state.

If you need a non-default trainer entrypoint, pass `--target-command` or `--target-command-json` to `run_ab_test.py` and `run_validations.py`.

## Exact Artifact Paths

The reproducible public story lives under [`showcase/the-remembering-scientist`](showcase/the-remembering-scientist):

- `01_seed_snapshot/MANIFEST.json`
- `01_seed_snapshot/ARTIFACT_REFERENCES.json`
- `compare.json`
- `compare.md`
- `candidate_summary.json`
- `validations/candidate_pool.json`
- `validations/confirm_comparison.json`
- `validations/audit_comparison.json`
- `validations/clean_replays.json`
- `validations/validation_summary.json`
- `figures/hero_curve.json`
- `figures/morning_report_comparison.json`
- `figures/retrieval_panels.json`
- `figures/lineage_graph.json`
- `figures/audit_panel.json`
- `figures/repeated_dead_end.json`
- `CASE_STUDY_DRAFT.md`

Each arm also keeps its own isolated workspace:

- `pair_XX/remembering/`
- `pair_XX/amnesiac/`

Inside each arm workspace, the most important trust-bearing artifacts are:

- `lab.sqlite3`
- `artifacts/reports/<campaign>/<date>/report.json`
- `artifacts/reports/<campaign>/<date>/report.md`
- `artifacts/proposals/<proposal_id>/...` when proposal export artifacts exist

## Exact Evidence Path

The showcase is now evidence-traced in the same way normal lab runs are:

- generated proposals carry `retrieval_event_id` and `evidence[]`
- retrieval lineage is persisted in SQLite through `retrieval_events`, `retrieval_event_items`, and `proposal_evidence_links`
- morning reports expose `current_best_candidate`, `top_failures`, recommendation notes, and memory coverage metrics
- `validations/validation_summary.json` consolidates:
  - `memory_citation_examples`
  - `candidate_lineage_references`
  - `repeated_dead_end_metrics`
  - exact paths for confirm, audit, and replay artifacts

If you want to inspect the public story from raw data upward, start with:

1. `compare.json`
2. `validations/validation_summary.json`
3. each arm's `report.json`
4. the candidate proposals referenced by the finalists

If you want a single mechanical trust check before reading the narrative, run `tools/verify_showcase_bundle.py` first.

## Honest Current Claim

The honest claim is still narrow:

`In a bounded one-GPU A/B pilot, the remembering arm increases evidence citation density and historical grounding, while final winners can still go either way after confirm, audit, and replay checks.`

That is a research claim about this bounded setup, not a claim about the whole lab and not a general claim of universal superiority.

## Caveats That Still Matter

- The historical pilot notes under `showcase/the-remembering-scientist/archive/` are real records, but some were written before the current evidence-traced reporting path existed.
- The eval path is still noisy enough that raw search wins alone are not trustworthy.
- One bounded A/B pair is not enough to claim broad superiority.
- `audit` and `replay` are robustness tools; they should sharpen the story, not be rewritten into marketing certainty.

## What Should Match Exactly

If this showcase is healthy, the same terminology should agree across the repo:

- `confirm`: promotion review on the primary search split
- `audit`: robustness review on `audit_val`
- `replay`: locked publication check on `locked_val`

If any doc or artifact says otherwise, trust the runtime behavior and fix the doc.
