# Implementation plans overview

This document describes the repo's current planning posture.

The historical buildout plans are archived under `docs/archive/exec-plans/`.
They are useful as implementation history, not as the main operator path.

## Current priorities

The current direction is:

1. keep live code as the source of live semantics
2. compress the common operator path
3. harden the critical seams around run, night, report, doctor, and cleanup
4. make reports and showcase claims sharper and more trustworthy
5. archive or delete docs that no longer earn their keep

## What must remain true

- structured artifacts and SQLite remain the control plane
- migrations are additive files under `sql/`
- proposal `family` and `kind` remain separate
- campaign comparability is explicit, never inferred
- raw search wins and validated champions are distinct states
- runtime autotune may change execution overlays, not scientific identity
- docs, specs, schemas, and tests move with code
- new complexity must justify itself in throughput, reliability, or legibility

## Core references

- `CODEX_GUARDRAILS.md`
- `ARCHITECTURE.md`
- `docs/runbook.md`
- `docs/product-specs/index.md`
- `docs/product-specs/acceptance-matrix.md`
- `docs/product-specs/ten-of-ten-signoff.md`

## Quality bar

The repo should feel like:

- an actual local research organization
- not a stitched-together MVP
- not a generic framework
- not a one-branch hill climber
- a repo that can defend its public claims with stored evidence
