# Showcase Writeup Template

## Claim

Same GPU. Same campaign. Same budget. The only difference was memory.

## Protocol Freeze

- Repo commit: `{{repo_commit}}`
- Campaign: `{{campaign_id}}`
- Pair count: `{{aggregate.pair_count}}`
- Snapshot manifest: `{{snapshot_manifest_path}}`

## Official A/B Summary

- Raw wins: `{{aggregate.wins_by_best_raw_metric}}`
- Mean best metric by arm: `{{aggregate.mean_best_metric_by_arm}}`
- Mean repeated-dead-end rate by arm: `{{aggregate.mean_repeated_dead_end_rate_by_arm}}`
- Mean memory citation coverage by arm: `{{aggregate.mean_memory_citation_coverage_by_arm}}`

## Confirm Results

- Remembering finalist: `{{final_primary_comparison.remembering}}`
- Amnesiac finalist: `{{final_primary_comparison.amnesiac}}`

## Audit Results

- Remembering audit: `{{final_audit_comparison.remembering}}`
- Amnesiac audit: `{{final_audit_comparison.amnesiac}}`

## Memory Story

- Citation examples: `{{memory_citation_examples}}`
- Candidate lineage references: `{{candidate_lineage_references}}`

## Figure Inputs

- `figures/hero_curve.json`
- `figures/morning_report_comparison.json`
- `figures/retrieval_panels.json`
- `figures/lineage_graph.json`
- `figures/audit_panel.json`
- `figures/repeated_dead_end.json`

## Repro Appendix

- Compare JSON: `{{compare_json_path}}`
- Validation summary JSON: `{{validation_summary_path}}`
- Clean replays JSON: `{{clean_replays_path}}`
