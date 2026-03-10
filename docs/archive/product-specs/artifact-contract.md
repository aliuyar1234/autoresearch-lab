# Artifact contract

Artifacts are local durable outputs of the lab.
They are the filesystem mirror of the ledger.

## Artifact roots

Primary default roots:
- `artifacts/runs/`
- `artifacts/reports/`
- `artifacts/proposals/`
- `artifacts/cache/`
- `artifacts/archive/`

These roots are local and gitignored.

## Per-run layout

Required base layout:
```text
artifacts/runs/<experiment_id>/
  manifest.json
  proposal.json
  config.json
  env.json
  stdout.log
  stderr.log
  summary.json
  artifact_index.json
```

Recommended optional layout:
```text
  metrics.jsonl
  notes.md
  patch.diff
  checkpoints/
    pre_eval.safetensors
    pre_eval.meta.json
  diagnostics/
    cuda_env.txt
    nvidia_smi.txt
```

## Artifact index

Each run root must contain `artifact_index.json`, validated by `schemas/artifact_index.schema.json`.

It must list every retained artifact with:
- `kind`
- `relative_path`
- `sha256`
- `size_bytes`
- `retention_class`
- `content_type`
- `created_at`

## Required artifact kinds

At minimum support:
- `manifest`
- `proposal`
- `config`
- `env`
- `stdout`
- `stderr`
- `summary`
- `metrics`
- `checkpoint`
- `patch`
- `report`
- `diagnostic`

## Retention classes

Suggested classes:
- `ephemeral`
- `discardable`
- `promoted`
- `champion`
- `crash_exemplar`
- `report`
- `campaign_asset`

Retention classes drive cleanup.
They must not be inferred from filenames alone.

## Artifact content rules

### Allowed default formats
Preferred:
- JSON / JSONL
- Markdown
- SQLite
- safetensors
- NumPy (`.npy`, `.npz`)
- plain text

### Avoid by default
- pickle
- arbitrary `torch.save` blobs for long-lived assets
- gigantic opaque binaries without metadata

## Path safety

Cleanup code may only delete inside managed artifact roots.
Artifact paths stored in SQLite must be relative to a configured artifact root or clearly marked absolute when unavoidable.

## Champion archive

For champion or promoted runs, create a durable archive record:
- copy or link selected artifacts into `artifacts/archive/`
- include champion card / summary note
- record lineage and why it was kept

## Report artifacts

Morning reports should live under:
`artifacts/reports/<date>/<campaign_id>/`

Required files:
- `report.md`
- `report.json`
- optional `report.html`

## Compression

Compression is optional.
If used:
- keep the artifact index uncompressed
- record compression method
- do not make routine inspection painful
