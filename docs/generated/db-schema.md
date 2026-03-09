# Database schema summary

This is the human-readable summary of `sql/001_ledger.sql`.

## Tables

### `campaigns`
Stores committed campaign manifests and basic queryable metadata.

Key columns:
- `campaign_id`
- `version`
- `comparability_group`
- `primary_metric_name`
- `manifest_json`

### `proposals`
Stores research hypotheses before, during, and after execution.

Important columns:
- `proposal_id`
- `campaign_id`
- `family`
- `kind`
- `lane`
- `status`
- `generator`
- `parent_ids_json`
- `complexity_cost`
- `config_overrides_json`
- `proposal_json`

### `experiments`
Stores per-run execution outcomes.

Important columns:
- `experiment_id`
- `proposal_id`
- `campaign_id`
- `lane`
- `status`
- `disposition`
- `crash_class`
- `proposal_family`
- `proposal_kind`
- `complexity_cost`
- `primary_metric_name`
- `primary_metric_value`
- `metric_delta`
- `tokens_per_second`
- `peak_vram_gb`
- `summary_path`
- `artifact_root`

### `artifacts`
Stores retained artifact index rows.

### `champions`
Stores campaign-local champion and archive-bucket membership.

### `daily_reports`
Stores generated report paths and summary counts.

## Design notes

- proposals and experiments are separate because one proposal may be replayed or confirmed many times
- proposal `family` and proposal `kind` are both persisted because they answer different questions
- reports should be derivable from the DB plus artifacts without scraping logs
