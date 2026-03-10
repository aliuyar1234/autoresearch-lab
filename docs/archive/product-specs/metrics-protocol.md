# Metrics protocol

This document defines how runtime metrics should be recorded.

## Goals

- machine-readable
- campaign-comparable where intended
- cheap to emit
- clear units
- no hidden semantics

## Canonical files

Every run should be able to emit:

- `summary.json`
- optional `metrics.jsonl`

## `summary.json`

`summary.json` is required and represents the final structured outcome.

### Required numeric fields and units

- `budget_seconds` — wall-clock seconds budgeted for the run
- `train_seconds` — measured training section time in seconds
- `eval_seconds` — measured evaluation section time in seconds
- `tokens_processed` — integer token count processed for training
- `tokens_per_second` — training tokens divided by `train_seconds`
- `peak_vram_gb` — peak allocated or reserved GPU memory in GiB-equivalent reporting units
- `primary_metric_value` — value of campaign primary metric

### Recommended fields

- `compile_seconds`
- `steady_state_mfu`
- `param_count`
- `checkpoint_path`
- `promotion_hint`
- `second_metric_values`

### Required identity fields

- `experiment_id`
- `proposal_id`
- `campaign_id`
- `lane`
- `status`
- `primary_metric_name`
- `backend`
- `device_profile`
- `seed`
- `config_fingerprint`
- `git_commit`
- `summary_version`

## `metrics.jsonl`

`metrics.jsonl` is optional but strongly recommended.

Each line should be a compact event object such as:
- training progress
- compile finished
- eval started
- eval finished
- checkpoint written

### Recommended line fields

- `event`
- `t_rel_seconds`
- `step`
- `tokens_processed`
- `loss`
- `lr`
- `grad_norm`
- `peak_vram_gb`
- `notes`

Do not emit unbounded verbose trace spam here.

## MFU guidance

MFU may be approximate.
That is acceptable.

But:
- record how it was computed
- record device profile
- never let MFU decide promotion on its own

## Missing values

If a metric is unavailable:
- prefer `null`
- do not invent sentinel magic numbers
- explain the missing value in `warnings` if it matters

## Rounding policy

Store raw values in JSON.
Only round in reports.
