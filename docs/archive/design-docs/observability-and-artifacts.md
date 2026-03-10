# Observability and artifacts

## Principle

The lab should never force the user to reconstruct a run from vague terminal scrollback.

## Artifact layout per experiment

Each experiment should have an artifact directory like:

```text
artifacts/runs/<experiment_id>/
  manifest.json
  proposal.json
  config.json
  env.json
  stdout.log
  stderr.log
  metrics.jsonl
  summary.json
  patch.diff
  notes.md
  checkpoints/
    pre_eval.safetensors
    pre_eval.meta.json
```

Not every file must exist for every run, but `manifest.json`, `config.json`, and a terminal `summary.json` always must.

## Structured summaries

The training target must emit a machine-readable terminal summary.
The runner should not scrape arbitrary logs as the primary truth.

Preferred pattern:
- final JSON written by the target
- runner copies or validates it
- human-readable summary may still be printed to stdout

## Metrics stream

`metrics.jsonl` should be append-only and include records such as:
- timestamp
- step
- loss
- lr multiplier
- tokens/sec
- mfu
- vram
- progress
- epoch
- warning flags

## Human notes

`notes.md` is optional but useful for:
- scheduler commentary
- why a run was promoted/discarded
- manual annotations after inspection

## Reports

Reports are generated from SQLite + artifacts, not from memory.

## Retention policy

Keep artifacts for:
- champions
- promoted runs
- crash exemplars
- latest daily reports
- representative near-misses

Allow cleanup of:
- redundant non-promoted intermediates
- stale checkpoints
- old scratch files
