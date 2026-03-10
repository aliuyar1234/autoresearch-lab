# Seed Snapshot Status

Status: frozen and cloned into remembering workspace

## Current State

There is currently no meaningful historical `base_2k` memory snapshot in the main repo-default lab state.

Observed repo state during prep:

- repo-default `base_2k` experiment count: `0`
- repo-default archive buckets: empty
- repo-default latest report: none

That repo-default state is still too thin, but the non-official `seed_builder` session now provides a usable frozen historical notebook for the remembering arm.

## Candidate Seed Sources Available Right Now

Currently available frozen seed material:

- non-official `seed_builder` session history
- copied SQLite ledger under `01_seed_snapshot/lab.sqlite3`
- copied proposals, archive state, and report bundle under `01_seed_snapshot/`

Why the earlier state was insufficient:

- the repo-default state had no `base_2k` history
- the early baseline-noise workspace had only baseline-family replays

## Minimum Seed Requirement Before Official A/B

Before official remembering-vs-amnesiac runs start, the remembering arm should have a frozen seed snapshot that includes at least:

- one baseline run
- multiple non-baseline proposals
- at least one failure or clear discard
- at least one near-miss or archived candidate
- at least one generated report bundle

## Current Decision

The non-official `seed_builder` session satisfies the minimum seed requirement for the bounded pilot.

Official launch policy now adopted:

- official search arms use `--hours 4 --max-runs 12`
- the run cap is intentional because current runs finish far earlier than the nominal campaign wall-clock budget

There is no remaining seed-side blocker before official A/B.
