# Implementation plans overview

This document is the high-level execution map for the current `8.6 -> 10` roadmap.

The detailed work lives in `docs/exec-plans/active/`, but this file explains how the phases fit together and what must remain true across them.

## Phase order

1. Phase 0 - migration substrate
2. Phase 1 - scientific correctness: eval splits + validation ladder
3. Phase 2 - evidence-traced memory
4. Phase 3 - compositional scheduler + negative memory
5. Phase 4 - RTX PRO 6000 runtime autotune
6. Phase 5 - evidence-grounded code lane
7. Phase 6 - flagship showcase automation
8. Phase 7 - identity cleanup + final signoff

## Why this order exists

The order is deliberate:

- correctness comes before polish
- evidence comes before public claims
- runtime tuning comes after the scientific contract is stable
- showcase work comes after validation, memory, and reporting are trustworthy
- signoff comes last so docs and metadata describe the real system, not an aspiration

## Cross-phase rules

These rules apply throughout all phases:

- structured artifacts and SQLite remain the control plane
- migrations are additive files under `sql/`, never hidden bootstrap magic
- proposal `family` and `kind` remain separate
- campaign comparability is explicit, never inferred
- raw search wins and validated champions are distinct states
- memory citations, repeated-dead-end metrics, and validation pass rate stay first-class report concepts
- runtime autotune may change execution overlays, not scientific identity
- docs, specs, schemas, and tests move with code
- new complexity must justify itself in throughput, reliability, or legibility

## Required supporting references

For every phase, consult:

- `CODEX_GUARDRAILS.md`
- `ARCHITECTURE.md`
- `docs/runbook.md`
- `docs/design-docs/file-by-file-blueprint.md`
- `docs/design-docs/algorithmic-appendix.md`
- `reference_impl/README.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`

## Phase completion checklist

A phase is complete only when:

- required files exist
- required tests exist and pass
- acceptance criteria in the phase doc are satisfied
- docs/specs/schemas remain aligned
- `docs/QUALITY_SCORE.md` reflects the current state
- `docs/generated/resolved-ambiguities.md` records any contract-level interpretation change

## Final quality bar

The end state should feel like:

- an actual local research organization
- not a stitched-together MVP
- not a generic framework
- not a one-branch hill climber
- not a lab that needs the human to remember hidden context
- a repo that can defend its public claims with stored evidence
