# Product acceptance matrix

This matrix defines the minimum bar for calling the repo a real lab rather than an impressive demo.

## 10/10 matrix

| Score | Area | Acceptance bar |
|---|---|---|
| 1/10 | Identity and golden path | package metadata, README, and top-level docs describe `Autoresearch Lab` accurately and make one operator path obvious |
| 2/10 | Migration substrate | multi-file SQL migrations under `sql/` are the normal path and `schema_migrations` proves versioned application |
| 3/10 | Canonical campaign truth | `base_2k` is mechanically honest about its data, tokenizer, and split contracts, and `eval_split` / `run_purpose` stay explicit |
| 4/10 | Validation ladder | confirm, audit, and locked review flows exist, are persisted, and can promote or reject candidates reproducibly |
| 5/10 | Evidence memory | proposals, retrieval events, and memory records can carry first-class evidence citations and lineage |
| 6/10 | Scheduler and archive | composition, dead-end avoidance, archive snapshots, and repeated-dead-end metrics exist in code and reports |
| 7/10 | Runtime execution | backend choice, autotune overlays, runtime-effective config, and VRAM/runtime metadata are persisted without changing scientific identity |
| 8/10 | Code lane and capability discipline | exported code proposal packs are evidence-grounded, returned patches/worktrees preserve lineage, and secondary capabilities are clearly demoted when not core |
| 9/10 | Proof paths | the lab has one canonical endurance path and the showcase has one canonical verifier-backed proof path |
| 10/10 | Trust, parity, and signoff | docs, schemas, tests, parity reporting, and lightweight signoff artifacts are aligned enough that the repo can defend its public claims |

## Full-project signoff checklist

The project may be called complete only when all of the following are true:

- [ ] `uv run arlab bootstrap` initializes a clean repo and applies all migrations
- [ ] `uv run arlab preflight --campaign base_2k` succeeds on the target workstation
- [ ] `uv run arlab campaign build --campaign base_2k` materializes assets with explicit eval splits
- [ ] `uv run arlab autotune --campaign base_2k --all-lanes` produces reusable runtime overlays
- [ ] `uv run arlab run --campaign base_2k --generate structured --lane scout` completes and records artifacts
- [ ] `uv run arlab validate --experiment <id> --mode confirm` can turn a raw candidate into a validated promotion
- [ ] `uv run arlab memory inspect --campaign base_2k` shows evidence-bearing memory records
- [ ] at least one code proposal pack can be exported and imported with evidence context intact
- [ ] `docs/OPERATING_CONTRACT.md`, `docs/RESEARCH_CONTRACT.md`, and `docs/AGENT_SESSION_CONTRACT.md` match the live repo
- [ ] `uv run python tools/parity_harness.py --json` reports the current upstream-vs-lab contract without pretending the paths are identical
- [ ] `uv run arlab night --campaign base_2k --hours 8 --allow-confirm` remains the official endurance proof path
- [ ] `python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm` can generate compare-ready showcase state
- [ ] `python tools/verify_showcase_bundle.py --showcase-root showcase/the-remembering-scientist --db-path showcase/the-remembering-scientist/pair_01/remembering/lab.sqlite3 --json` can mechanically verify the published showcase bundle
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
