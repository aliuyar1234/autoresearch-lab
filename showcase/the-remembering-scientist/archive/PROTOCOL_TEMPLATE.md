# Protocol Template

## Frozen Baseline

- Repo commit: `{{repo_commit}}`
- Primary campaign: `{{campaign_id}}`
- Snapshot manifest: `{{snapshot_manifest_path}}`
- Pair count: `{{pair_count}}`
- Hours per arm: `{{hours}}`
- Max runs per arm: `{{max_runs}}`

## Fairness Rules

- same repo commit
- same campaign manifest
- same runner and scheduler logic
- same target command template
- same device profile and backend policy
- remembering arm gets frozen historical memory
- amnesiac arm gets empty historical state

## Official Order

- pair order mode: `{{order}}`
- seed policy: `{{seed_policy}}`
- allow confirm during search: `{{allow_confirm}}`

## Validation Plan

- top candidates per arm: `{{top_per_arm}}`
- confirm mode: `confirm`
- audit mode: `audit`
- publication replay split: `locked_val`

## Artifact Requirements

- `compare.json`
- `validations/candidate_pool.json`
- `validations/confirm_comparison.json`
- `validations/audit_comparison.json`
- `validations/clean_replays.json`
- `figures/*.json`
- `CASE_STUDY_DRAFT.md`
