# Phase 2 — Campaign assets and offline data path

Status: planned

## Objective

Move campaign data preparation out of the hot execution loop and establish durable asset manifests.

## Deliverables

1. campaign manifest loader and validator
2. campaign build/verify CLI
3. offline tokenization path
4. offline packing path
5. generated asset manifests and integrity checks
6. campaign tests

## Exact files to create

Required new files:
- `lab/campaigns/__init__.py`
- `lab/campaigns/load.py`
- `lab/campaigns/build.py`
- `lab/campaigns/verify.py`
- `lab/campaigns/packing.py`
- `lab/campaigns/builders/__init__.py`
- `lab/campaigns/builders/base_2k.py`
- `lab/campaigns/builders/stories_2k.py`
- `lab/campaigns/builders/long_4k.py`
- `schemas/campaign.schema.json`
- `tests/unit/test_campaign_validation.py`
- `tests/unit/test_offline_packing.py`
- `tests/integration/test_campaign_build_verify.py`

Required file updates:
- `lab/cli.py`
- `campaigns/*/campaign.json`
- `templates/*.json`

## Required references

Read before implementing:
- `docs/design-docs/data-pipeline-and-campaigns.md`
- `docs/design-docs/algorithmic-appendix.md`
- `reference_impl/offline_packing.py`
- `reference_impl/campaign_split_rules.py`

## Tasks

### F2.1 — Campaign load and validation
Load campaign manifests, validate against schema, and expose typed accessors.

### F2.2 — Asset manifest format
Define tokenizer, pretok, and packed manifests with hashes and build metadata.

### F2.3 — Offline tokenization
Materialize tokenized documents to durable assets.

### F2.4 — Offline packing
Implement deterministic BOS-aligned packing of tokenized chunks into fixed-length blocks.
Acceptance:
- repeated builds on the same assets produce identical packed outputs

### F2.5 — Verify command
Add `campaign verify`.
Acceptance:
- hash mismatches fail loudly
- missing required assets are reported clearly

### F2.6 — Base campaigns
Implement builders for:
- `base_2k`
- `stories_2k`
- `long_4k`

Acceptance:
- `base_2k` uses explicit held-out shards
- `stories_2k` uses deterministic partitioning
- `long_4k` stays campaign-local

## Acceptance criteria

Phase 2 is complete when:

- campaign manifests validate
- `campaign build` is idempotent
- offline packing is deterministic
- `campaign verify` catches broken assets
- the train path no longer needs to do expensive per-run packing work for campaign-built assets

## Non-goals

Do **not** in Phase 2:
- redesign the research model
- build a generic dataset framework
- rank campaigns against each other
