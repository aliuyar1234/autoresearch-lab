# Data pipeline and campaigns

## Why this subsystem matters

In upstream, part of the fixed 5-minute budget is spent on tokenization and Python-side packing.
That was the right tradeoff for a tiny repo.
It is not the right tradeoff for a real lab.

## Campaign abstraction

A campaign defines:

- dataset adapter
- asset version
- tokenizer config
- sequence length
- train/eval split rules
- budget lanes
- primary metric
- qualitative probes
- retention policy

Campaigns make the lab useful beyond one static baseline while preserving comparability within a campaign.

## Required v1 campaigns

### `base_2k`
Purpose:
- faithful upstream-style main campaign
- same spirit as current repo
- primary regression and parity target

### `stories_2k`
Purpose:
- narrower, faster qualitative feedback loop
- useful for verifying improvements on a low-entropy corpus

### `long_4k`
Purpose:
- exploit the workstation's large VRAM
- stress long-context/back-end/data-path behavior
- separate campaign because not directly comparable to `base_2k`

## Asset pipeline

The new data path should produce:

1. raw download manifest
2. tokenizer asset manifest
3. pretokenized shard cache
4. prepacked block cache
5. integrity hashes
6. human-readable campaign manifest

## Packer requirements

The packer should preserve the upstream idea:
- BOS-aligned packing
- best-fit-ish utilization
- no meaningless padding if avoidable

But it should move the expensive work out of the hot training path.

## Dataloader requirements

The training path should be able to:
- mmap or otherwise efficiently stream packed blocks
- use pinned host memory
- overlap host->device copies where useful
- remain simple enough to debug

## Asset safety rules

Avoid unsafe serialization.
Prefer:
- JSON for manifests
- plain files for tokenizer merges/patterns
- NumPy/safetensors for binary arrays where appropriate

## Campaign-local comparability

Never rank results across campaigns as if they are directly comparable.
Instead:
- maintain per-campaign leaderboards
- maintain per-campaign archive
- maintain per-campaign report sections
