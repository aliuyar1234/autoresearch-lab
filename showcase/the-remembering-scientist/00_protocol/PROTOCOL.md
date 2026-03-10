# The Remembering Scientist - 12h Pilot Protocol

Status: historical frozen protocol used for the executed pilot

## Purpose

This protocol governs the bounded 12-hour pilot for `The Remembering Scientist`.

This is a pilot, not the full flagship. Its purpose is to determine whether the memory-vs-amnesia story is strong enough to justify the larger multi-night showcase.

## Core Claim

Same GPU. Same campaign. Same budget. The only difference was memory.

For the bounded pilot, the intended public claim is narrower:

- the remembering lab searches more strategically
- the remembering lab wastes fewer experiments
- the remembering lab leaves a more coherent research trail

The pilot does not attempt to prove universal superiority or full cross-campaign robustness.

## Frozen Baseline

- Repo commit: `f4236c720832bdb0916012f7e47e586b8372e14d`
- Primary campaign manifest: `campaigns/base_2k/campaign.json`
- Primary campaign SHA256: `7CA07915A7E97E3D9E475CBAF473CB2D84CAC9F83C9A3A6C5394A6F2156776F3`
- Secondary audit candidate manifest: `campaigns/stories_2k/campaign.json`
- Secondary audit candidate SHA256: `744101E4D7521C00F6EDF4241AE85B28576D832F38030689055205615E51967D`

## Official Pilot Scope

The bounded pilot is fixed to a 12-hour operator envelope with explicit run caps:

- official `remembering` session: up to `4h` wall-clock or `12` runs, whichever comes first
- official `amnesiac` session: up to `4h` wall-clock or `12` runs, whichever comes first
- confirm replay of top `remembering` candidate: up to `1h`
- confirm replay of top `amnesiac` candidate: up to `1h`
- clean baseline replay: up to `1h`
- clean replay of the stronger finalist: up to `1h`

Anything outside this envelope is prep, instrumentation, or future work and must not be presented as part of the official 12-hour comparison.

## Launch Blocker Discovered During Prep

The current trainer is not consuming the nominal wall-clock budgets the way the campaign manifest suggests during these short runs. In practice, recent scout and main runs are finishing in only a few to a few dozen seconds because they hit internal step limits early.

Operational consequence:

- a literal uncapped 4-hour official session would generate a very large number of runs
- each run currently retains a pre-eval checkpoint artifact
- this would create a low-signal, high-artifact-churn official session

Therefore the official launch policy for this pilot is tightened as follows:

- every official search arm must use `--max-runs 12`
- the `--hours` bound remains in place as a hard ceiling, but the run cap is the practical limiter
- confirm and replay steps remain single-run bounded checks

This keeps the pilot honest and manageable without pretending the current trainer consumes the nominal campaign budgets literally.

## Primary Campaign Decision

Primary campaign for the bounded pilot:

- `base_2k`

Reason:

- fully verified on this workstation
- closest to upstream spirit
- stable parity-oriented campaign
- already has clean preflight and asset verification

## Audit Simplification For The 12h Pilot

The full flagship plan wanted one separate audit campaign. For the 12-hour pilot, external audit is simplified.

Decision:

- do not require a separate external audit campaign during the 12h pilot
- use `base_2k` only for the official pilot
- rely on the campaign's internal held-out mixture and confirm replays for bounded robustness evidence
- defer sibling-campaign audit to a later stage unless `stories_2k` raw source data is staged

Reason:

- `stories_2k` is defined but not turnkey on this machine yet
- its builder expects a local plain-text source corpus under `artifacts/cache/raw/tinystories-gpt4-clean`
- current repo state does not include that source corpus

This simplification is intentional and must be disclosed if pilot results are published.

## Fairness Rules

Everything below must be identical between the two arms:

- repo commit
- campaign manifest
- runner version
- proposal generator version
- scheduler policy
- promotion thresholds
- machine and GPU
- time budget
- confirm protocol
- static docs and instructions
- manual intervention policy

The only intended difference:

- `remembering` may access a frozen historical memory snapshot
- `amnesiac` may not access historical memory

## Shared Context

Both arms may access:

- `AGENTS.md`
- `README.md`
- `docs/runbook.md`
- this protocol pack
- campaign manifests
- machine profile
- static lab rules

## Historical Memory Split

Remembering-only memory may include:

- historical experiment summaries
- prior proposal/result pairs
- prior archive state
- prior failure patterns
- prior report bundles

Amnesiac must not access:

- frozen historical SQLite state
- historical run artifacts
- historical reports
- manually injected prior findings

Amnesiac is still allowed:

- same-session queue state
- same-session leaderboard state
- same-session archive updates
- same-session report generation

## Workspace Layout

The pilot must use isolated managed roots instead of the repo-default roots.

Planned workspaces:

- `showcase/the-remembering-scientist/workspaces/baseline_noise`
- `showcase/the-remembering-scientist/workspaces/remembering`
- `showcase/the-remembering-scientist/workspaces/amnesiac`

Each workspace should own:

- `artifacts/`
- `cache/`
- `.worktrees/`
- `lab.sqlite3`

The repo root remains shared and fixed.

## Official Session Order

For the bounded 12-hour pilot:

1. baseline noise estimation
2. memory-seed freeze
3. official `remembering` session
4. official `amnesiac` session
5. confirm replays
6. clean publication replays

No official A/B run may start until:

- protocol is frozen
- baseline noise is measured
- memory seed is frozen
- both arm workspaces are prepared
- official launch policy is fixed to `--max-runs 12`

## Publishability Boundaries

The 12-hour pilot may support:

- teaser writeup
- case study
- internal go/no-go decision for the full flagship

The 12-hour pilot does not support:

- broad "better than upstream in general" claims
- strong cross-campaign robustness claims
- full flagship publication without clear caveats
