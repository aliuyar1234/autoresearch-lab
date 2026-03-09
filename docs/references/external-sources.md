# External sources and why they matter

This repo pack is self-sufficient, but these sources explain the product philosophy and hardware/runtime context.

## 1. Karpathy `autoresearch` upstream

URL:
- https://github.com/karpathy/autoresearch

Why it matters:
- defines the baseline taste and minimal concept
- establishes the original loop: fixed preparation, mutable trainer, one metric, keep/discard logic
- should be treated as the seed, not something to erase

Most relevant files:
- `README.md`
- `program.md`
- `prepare.py`
- `train.py`
- `pyproject.toml`

A local snapshot is included under:
- `docs/references/upstream_snapshot/`

## 2. OpenAI — Harness engineering

URL:
- https://openai.com/index/harness-engineering/

Why it matters:
- argues that repository-local structure is the real substrate for strong coding agents
- emphasizes repository knowledge as the system of record
- emphasizes agent legibility and architecture enforcement
- motivates the split between design docs, product specs, execution plans, fixtures, and guardrails

A local adaptation is included under:
- `docs/references/harness-engineering-summary.md`

## 3. NVIDIA RTX PRO 6000 Blackwell workstation GPU

URL:
- https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/

Why it matters:
- representative target machine for this lab direction
- 96 GB VRAM means the lab can emphasize larger device batch, confirm lanes, and 4k campaigns without becoming distributed

## Important note

Codex should not rely on live browsing to understand the product.
These references are here to justify design choices and to help verify implementation details when online access exists.
