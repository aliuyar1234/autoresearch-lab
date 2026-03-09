# Implementation plans overview

This document is the high-level execution map.

The detailed work lives in `docs/exec-plans/active/`, but this file explains how the phases fit together and what must remain true across them.

## Phase order

1. Phase 0 — Foundation and repository operating system
2. Phase 1 — Runner, ledger, and artifact core
3. Phase 2 — Campaign assets and offline data path
4. Phase 3 — Evaluation ladder, scoring, replay
5. Phase 4 — Scheduler, archive, and proposal system
6. Phase 5 — Dense search surface and backend integration
7. Phase 6 — Reports, night runs, and campaign UX
8. Phase 7 — Reliability, cleanup, and final polish

## Cross-phase rules

These rules apply throughout all phases:

- baseline parity path stays runnable until explicitly retired
- proposal `family` and `kind` remain separate
- structured artifacts and SQLite remain the control plane
- campaign comparability is explicit, never inferred
- docs/specs/tests move with code
- new complexity must justify itself in throughput, reliability, or legibility

## Required supporting references

For every phase, Codex should also consult:

- `CODEX_GUARDRAILS.md`
- `docs/design-docs/file-by-file-blueprint.md`
- `docs/design-docs/algorithmic-appendix.md`
- `docs/design-docs/codex-drift-risks.md`
- `reference_impl/README.md`

## Phase completion checklist

A phase is complete only when:

- required files exist
- required tests exist and pass
- acceptance criteria in the phase doc are satisfied
- docs/specs/schemas remain aligned
- `docs/QUALITY_SCORE.md` is updated
- any interpretation changes are recorded in `docs/generated/resolved-ambiguities.md`

## Final quality bar

The end state should feel like:
- an actual local research organization
- not a stitched-together MVP
- not a generic framework
- not a one-branch hill climber
- not a lab that needs the human to remember hidden context
