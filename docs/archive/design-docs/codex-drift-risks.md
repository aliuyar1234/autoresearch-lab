# Codex drift risks

This document names the specific fantasies or wrong turns an implementation agent is most likely to take.

Each risk includes the intended correction.

## Drift risk 1: building a framework instead of a lab

Symptoms:
- registries everywhere
- “provider” abstractions
- plugin systems
- command buses
- YAML forests
- generic experiment services

Correction:
- use plain modules
- keep boundaries explicit
- if a thing has one implementation, give it one implementation

## Drift risk 2: making everything configurable

Symptoms:
- dozens of config knobs before a clear default path exists
- campaign manifests that stop being human-readable
- runtime flags that duplicate campaign semantics

Correction:
- campaign manifests define comparability
- CLI flags are operator controls, not campaign rewrites
- structured search space must stay bounded and explicit

## Drift risk 3: letting raw logs become the control plane

Symptoms:
- scheduler reading `stderr.log` to infer decisions
- runner using grep instead of summary artifacts
- report generation relying on terminal text

Correction:
- control plane is JSON + SQLite
- logs are debugging artifacts only

## Drift risk 4: treating proposal family and implementation mode as one field

Symptoms:
- “structured” proposals with no family semantics
- reports unable to say exploit vs combine vs novel
- scheduler unable to reason about proposal intent

Correction:
- always track both:
  - `family`
  - `kind`

## Drift risk 5: leaving the hot path impure

Symptoms:
- online tokenization or packing still happens in every run
- backend microbench runs on every experiment
- campaign verification requires a full rebuild

Correction:
- campaign build is offline and idempotent
- backend choice is cached
- verify checks integrity, not recomputation

## Drift risk 6: overusing the code lane

Symptoms:
- Codex exports code proposals too early
- simple dense-search wins are skipped
- the repo starts mutating too many files for ordinary search

Correction:
- structured lane is the default
- code lane is for justified architecture or trainer changes only
- reports should explicitly say when a code proposal is warranted

## Drift risk 7: conflating campaigns

Symptoms:
- one leaderboard across incompatible sequence lengths or datasets
- reports comparing base-2k and long-4k as if they were directly comparable

Correction:
- leaderboards are campaign-local
- cross-campaign commentary is narrative only, never numeric ranking

## Drift risk 8: using VRAM abundance to bloat the baseline

Symptoms:
- gigantic default models
- poor step throughput
- fewer experiments per night

Correction:
- prioritize device batch, lower accumulation overhead, and confirm capacity first
- bigger models only when the data says they win in the fixed budget

## Drift risk 9: underbuilding reliability

Symptoms:
- checkpoint saved after eval rather than before
- partial runs lost on restart
- cleanup deleting files that reports or champions still need

Correction:
- manifest first
- checkpoint before risky eval
- conservative cleanup
- DB and artifact roots must agree

## Drift risk 10: making reports pretty but weak

Symptoms:
- charts without decisions
- walls of text without metrics
- no recommendation section
- no failure summary

Correction:
- the report should answer:
  - what improved
  - what failed
  - what was promoted
  - what is worth doing next

## Drift risk 11: hiding important semantics in chat instead of the repo

Symptoms:
- design decisions exist only in conversation
- Codex must remember things not written anywhere

Correction:
- every important decision must be written into:
  - docs
  - schemas
  - SQL
  - code comments
  - fixtures
  - generated ambiguity log

## Final rule

Whenever implementation feels “clever,” check whether the repo just became less legible.
If it did, simplify it.
