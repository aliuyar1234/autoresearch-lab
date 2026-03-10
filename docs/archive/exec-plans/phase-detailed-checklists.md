# Phase detailed checklists

This file complements the phase docs with anti-drift implementation checklists.

## Phase 0
Do:
- implement path safety early
- keep `lab.cli` thin
- add `.lab.env` support but make it optional

Do not:
- add business logic to import-time code
- add large dependencies

## Phase 1
Do:
- write manifest before launch
- use fake targets first
- classify failures deterministically

Do not:
- infer metrics from logs if `summary.json` exists
- skip schema validation

## Phase 2
Do:
- move tokenization and packing offline
- make campaign build idempotent
- write integrity manifests

Do not:
- leave online packing in the hot path for the campaign builder path
- mix campaign semantics in code comments only

## Phase 3
Do:
- keep promotion rule-based
- make replay produce a new experiment id
- checkpoint before risky evaluation

Do not:
- build a weighted-score soup
- hide promotion logic in report rendering

## Phase 4
Do:
- model `family` and `kind` separately
- dedupe by config fingerprint
- keep archive campaign-local

Do not:
- implement random mutation only
- treat code lane as the default path

## Phase 5
Do:
- make the structured search surface real
- cache backend decisions
- add tiny GPU smoke coverage

Do not:
- make the default model huge just because VRAM exists
- spread backend assumptions across random files

## Phase 6
Do:
- make reports opinionated and useful
- keep campaign leaderboards separate
- generate recommendations from structured data

Do not:
- build a dashboard
- produce giant wall-of-log reports

## Phase 7
Do:
- make cleanup conservative
- make resume reconstruct from DB plus artifacts
- add doctor diagnostics

Do not:
- delete retained artifacts
- start new architecture work during polish
