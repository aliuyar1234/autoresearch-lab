# Frozen Seed Manifest

Status: frozen from non-official seed-builder session

## Source Workspace

- `showcase/the-remembering-scientist/workspaces/seed_builder`

## Snapshot Contents

- copied SQLite ledger: `01_seed_snapshot/lab.sqlite3`
- copied proposal artifacts: `01_seed_snapshot/proposals`
- copied archive artifacts: `01_seed_snapshot/archive`
- copied report bundle: `01_seed_snapshot/reports`

## Seed Session Summary

- campaign: `base_2k`
- run count: `8`
- promoted count: `5`
- failed count: `1`
- queue refills: `2`

## Highest-Signal Seed Runs

- champion: `exp_20260310_000516+0000_83a9a1e5`
  - family: `combine`
  - metric: `11.408509`
  - key changes:
    - `curriculum.sequence_curriculum.enabled=True`
    - `model.rope_base=50000`

- prior strong run: `exp_20260310_000457+0000_365d7cfc`
  - family: `combine`
  - metric: `13.157294`

- prior strong run: `exp_20260310_000427+0000_73117ce3`
  - family: `novel`
  - metric: `13.923339`

## Failure And Discard Evidence

- failed run: `exp_20260310_000407+0000_9042e625`
  - family: `novel`
  - lane: `main`
  - crash class: `unknown`

- discarded run: `exp_20260310_000438+0000_8413ba44`
  - family: `novel`
  - metric: `18.020368`

- discarded run: `exp_20260310_000507+0000_6327c7db`
  - family: `combine`
  - metric: `19.121184`

## Report Bundle

Frozen report root:

- `showcase/the-remembering-scientist/01_seed_snapshot/reports/2026-03-10/base_2k`

Key recommendations preserved from the seed session:

- exploit `curriculum.sequence_curriculum.enabled`
- exploit `model.rope_base`
- avoid or ablate `curriculum.progressive_depth.enabled`

## Remembering Workspace Normalization

The remembering workspace was seeded from this snapshot, and any leftover queued proposals were normalized to `superseded` before official launch.
