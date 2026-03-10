# Model search space

## Goal

Expand the search surface substantially while staying:
- dense-model-first
- compile-friendly
- single-GPU-native
- understandable

## Search surface categories

### Architecture
- depth
- width / aspect ratio
- head dimension
- head count
- KV head ratio (full, half, quarter)
- window pattern
- optional periodic parameter sharing
- residual / x0 scalar policies
- RoPE base and rotary policy
- optional EMA-at-eval

### Optimization
- total batch size
- device batch size
- grad accumulation
- optimizer group LRs
- weight decay groups
- warmup / warmdown
- final LR fraction
- momentum schedule
- EMA decay

### Curricula
- progressive depth
- progressive window expansion
- sequence-length curriculum
- budget-aware curriculum

### Backend / runtime
- attention backend selection
- compile cache strategy
- backend blacklisting on failure

## Required structured knobs for v1

At minimum implement structured mutation for:
- `DEPTH`
- `ASPECT_RATIO`
- `HEAD_DIM`
- `N_KV_HEAD`
- `WINDOW_PATTERN`
- embedding / unembedding / matrix / scalar learning rates
- weight decay
- warmdown
- RoPE base
- EMA on/off
- sequence curriculum on/off
- progressive depth on/off

## Explicit non-goals

Do not turn this into:
- MoE / router research
- giant activation zoo
- every paper trick ever
- hard-to-compile dynamic graph chaos

## Code-lane ideas that are allowed

These are fair game for code proposal packs if structured search stalls:
- changing residual routing mechanics
- simplifying or improving value embeddings
- improved initialization
- better long-context scheduling
- alternative dense attention compositions
- cleanup that removes complexity while preserving results

## Philosophy

Most wins on one GPU come from better use of fixed wall-clock budget, not maximal architecture novelty.
The search space must reflect that.
