# Runner contract

The runner is the execution engine for one experiment.

## Runner responsibilities

For every experiment, the runner must:

1. allocate an experiment id
2. write `manifest.json` before launching training
3. snapshot proposal/config/environment
4. create stdout/stderr capture
5. execute the training target with explicit timeout/budget
6. checkpoint before final expensive evaluation when configured
7. collect terminal summary
8. classify disposition and crash class
9. update SQLite
10. return a stable result object to the CLI

## Canonical lifecycle states

The runner must model at least these states:

- `created`
- `preflight_ok`
- `materialized`
- `launching`
- `running`
- `checkpointed`
- `evaluating`
- `completed`
- `failed`
- `discarded`
- `promoted`
- `archived`

Not all are persisted as independent rows, but terminal state must be persisted.

## Terminal statuses

Valid terminal statuses:
- `completed`
- `failed`
- `discarded`
- `promoted`

`completed` means the run executed and summary was valid.
Promotion/discard is a disposition layered on top.

## Crash classes

The runner must assign one crash class on failure:

- `preflight_failed`
- `import_error`
- `compile_error`
- `oom_train`
- `oom_eval`
- `timeout`
- `nan_or_inf`
- `assertion_failure`
- `data_missing`
- `asset_corrupt`
- `backend_unavailable`
- `interrupted`
- `unknown`

Classification rule:
- choose the narrowest reliable class
- if uncertain, use `unknown`
- record a short human-readable excerpt

## Run directory contract

Each experiment has a root:
`artifacts/runs/<experiment_id>/`

Required files:
- `manifest.json`
- `proposal.json`
- `config.json`
- `env.json`
- `stdout.log`
- `stderr.log`
- `summary.json`
- `artifact_index.json`

Optional files:
- `metrics.jsonl`
- `notes.md`
- `patch.diff`
- `checkpoints/pre_eval.safetensors`
- `checkpoints/pre_eval.meta.json`

## Manifest requirements

`manifest.json` must include:
- experiment id
- proposal id
- campaign id
- lane
- seed
- time budget seconds
- run command
- working directory
- parent commit
- device profile
- selected backend
- proposal family
- proposal kind
- artifact root
- timestamps

May also include:
- replay source experiment id
- pre-eval checkpoint target path
- pre-eval checkpoint metadata path

## Summary requirements

The training target must emit or allow the runner to synthesize a final `summary.json`.

Minimum required summary fields:
- `experiment_id`
- `proposal_id`
- `campaign_id`
- `lane`
- `status`
- `primary_metric_name`
- `primary_metric_value`
- `budget_seconds`
- `train_seconds`
- `eval_seconds`
- `tokens_processed`
- `tokens_per_second`
- `peak_vram_gb`
- `backend`
- `device_profile`
- `seed`
- `config_fingerprint`
- `git_commit`
- `warnings` (array)
- `summary_version`

Strongly preferred:
- `proposal_family`
- `proposal_kind`
- `complexity_cost`
- `steady_state_mfu`
- `param_count`
- `compile_seconds`
- `promotion_hint`
- `checkpoint_path`
- `second_metric_values`

## Checkpoint-before-eval policy

For any lane that performs expensive or failure-prone final evaluation:
- save a pre-eval checkpoint if the run reached evaluation eligibility
- record checkpoint metadata in `pre_eval.meta.json`
- retain checkpoint at least until scoring and report generation complete
- cleanup policy may later delete it if not promoted

Preferred format:
- `safetensors` for model/EMA weights
- JSON for metadata

The runner should expose the checkpoint targets to the training target via explicit environment variables so the checkpoint path is stable and auditable:
- `LAB_PRE_EVAL_CHECKPOINT_PATH`
- `LAB_PRE_EVAL_META_PATH`

If the run is a replay, the runner should also expose:
- `LAB_REPLAY_SOURCE_EXPERIMENT_ID`

## Execution isolation

The runner may execute:
- directly in repo root for structured runs if no source mutation is required
- in a worktree for code-level proposals

It must always record:
- actual working directory
- git commit hash
- parent proposal references

## Time budget behavior

If a time budget exists:
- the runner must enforce it
- the training target should also be informed of it
- timeout must yield a structured terminal record, not a silent kill where possible

## Schema validation

Before marking a run successful:
- validate manifest against `schemas/run_manifest.schema.json`
- validate summary or synthesized experiment record against `schemas/experiment_record.schema.json`
- validate artifact index against `schemas/artifact_index.schema.json`

A schema failure is a run failure, not a warning.

## Determinism expectations

The runner is not responsible for making training perfectly deterministic.
It is responsible for making the run **auditable**:
- explicit seed
- explicit config
- explicit commit
- explicit backend
- explicit campaign version

## Testing requirements

The runner must have:
- unit tests for crash classification
- integration test for fake successful run
- integration test for fake failure run
- integration test for manifest/artifact creation
- smoke path proving one real tiny run can complete on GPU
