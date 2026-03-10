# Product acceptance matrix

This matrix defines the minimum bar for calling the repo a real lab rather than an impressive demo.

## 10/10 matrix

| Score | Area | Acceptance bar |
|---|---|---|
| 1/10 | Identity and metadata | package metadata, README, and top-level docs describe `Autoresearch Lab` accurately rather than an upstream prototype or "swarm" concept |
| 2/10 | Migration substrate | multi-file SQL migrations under `sql/` are the normal path and `schema_migrations` proves versioned application |
| 3/10 | Scientific correctness | `eval_split` and `run_purpose` are explicit, and raw search wins do not bypass validation |
| 4/10 | Validation ladder | confirm, audit, and locked review flows exist, are persisted, and can promote or reject candidates reproducibly |
| 5/10 | Evidence memory | proposals, retrieval events, and memory records can carry first-class evidence citations and lineage |
| 6/10 | Scheduler and archive | composition, dead-end avoidance, archive snapshots, and repeated-dead-end metrics exist in code and reports |
| 7/10 | Runtime execution | backend choice, autotune overlays, runtime-effective config, and VRAM/runtime metadata are persisted without changing scientific identity |
| 8/10 | Code lane | exported code proposal packs are evidence-grounded, returned patches/worktrees preserve lineage, and imported results become first-class lab runs |
| 9/10 | Reporting and showcase | morning reports surface validated outcomes, citation coverage, and repeated-dead-end rate, and the remembering-scientist showcase runs from code |
| 10/10 | Trust and signoff | docs, schemas, tests, and lightweight signoff artifacts are aligned enough that the repo can defend its public claims |

## Full-project signoff checklist

The project may be called complete only when all of the following are true:

- [ ] `python -m lab.cli bootstrap` initializes a clean repo and applies all migrations
- [ ] `python -m lab.cli preflight --campaign base_2k` succeeds on the target workstation
- [ ] `python -m lab.cli campaign build --campaign base_2k` materializes assets with explicit eval splits
- [ ] `python -m lab.cli autotune --campaign base_2k --all-lanes` produces reusable runtime overlays
- [ ] `python -m lab.cli run --campaign base_2k --generate structured --lane scout` completes and records artifacts
- [ ] `python -m lab.cli validate --experiment <id> --mode confirm` can turn a raw candidate into a validated promotion
- [ ] `python -m lab.cli memory inspect --campaign base_2k` shows evidence-bearing memory records
- [ ] at least one code proposal pack can be exported and imported with evidence context intact
- [ ] `python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k` can generate compare-ready showcase state
- [ ] reports clearly distinguish validated champions, failures, memory citations, and repeated-dead-end metrics
- [ ] cleanup can safely prune discardable artifacts
- [ ] GPU smoke passes on the target machine
- [ ] docs and schemas match implementation reality

## Public-claim rule

The repo is allowed to claim "world-class taste" only when:

- public claims point to stored evidence rather than vibes
- showcase claims can be regenerated from code
- raw search wins are not presented as validated proof
- the operator story is legible from the repo alone
