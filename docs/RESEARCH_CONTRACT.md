# Research Contract

This document defines how the repo should speak about scientific parity, the lab-native research surface, and advanced capabilities.

## Upstream Truth Anchor

The upstream baseline path still matters:

```bash
uv run prepare.py
uv run train.py
```

Its role is narrow and important:

- truth anchor for the original direct experiment loop
- truth anchor for 2048 / 8192 / 300-second semantics
- truth anchor for the original parquet + BPE data path
- regression anchor when the lab-native path evolves

It is not the day-to-day operator path.

## Lab-Native Scientific Path

The normal lab path is:

- campaign assets built locally
- structured proposals generated and persisted by the lab
- experiments executed through `research/dense_gpt/train.py`
- promotions gated by `confirm`
- robustness checked by `audit`

Its role is:

- the primary structured-search engine for normal lab operation
- the research surface the scheduler can mutate safely
- the path reports, memory, lineage, and validation are built around

## What Must Stay Explicit

The repo must not blur these differences:

- upstream uses direct parquet download and BPE tokenizer training
- canonical lab campaigns currently use local UTF-8 text files and deterministic byte-fallback tokenizer assets
- upstream evaluates over fixed `EVAL_TOKENS`
- the lab-native trainer defaults to bounded `eval_batches`
- upstream `train.py` still carries scientific mechanisms that are not identical to `research/dense_gpt/train.py`

Those are not embarrassments.
They are the current truth.

## Parity Harness

Use this command to report the current parity contract:

```bash
uv run python tools/parity_harness.py --json
```

Optional summary comparison:

```bash
uv run python tools/parity_harness.py --upstream-summary path/to/upstream_summary.json --lab-summary path/to/lab_summary.json --json
```

The parity harness is intentionally lightweight.
It is for semantic alignment and documented differences, not for pretending the two paths are identical.

## Scientific Core Position

`research/dense_gpt/` should be treated as:

- the primary structured-search engine for the lab
- the place where the lab gets controllable, repeatable proposal mutation
- a justified alternative to the upstream path only when it improves iteration, controllability, or trust

It should not be described as scientifically superior unless the evidence actually supports that claim.

## Capability Tiers

### Proven And Core

- SQLite ledger and migrations
- canonical campaign asset building
- explicit eval splits
- confirm / audit validation ladder
- unattended `night` sessions
- reports, doctor, and cleanup
- official proof paths

### Useful But Secondary

- runtime autotune overlays
- code proposal export/import
- reviewed scheduler-policy files and agent-authored policy suggestions
- non-canonical campaigns
- showcase automation

### Promising But Not Yet Proven

- memory as a repeatable scientific advantage
- archive-aware scheduling as a repeatable scientific advantage
- lab-native trainer superiority over the upstream trainer

## Naming Discipline

If a capability is in the "promising but not yet proven" tier:

- do not front-door it as the main reason the repo is better
- do not claim it as settled scientific advantage
- do not let it outrank the golden operator path in the docs

The repo should sound exactly as smart as the evidence allows.
