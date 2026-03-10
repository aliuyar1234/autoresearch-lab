# QUALITY_SCORE.md

This file tracks product maturity by domain.

Scoring scale:
- 0 = absent
- 1 = barely present / ad hoc
- 2 = functional but weak
- 3 = strong
- 4 = excellent

## Baseline imported from upstream concept

| Domain | Baseline | Target |
|---|---:|---:|
| Repo knowledge store | 1 | 4 |
| Runner / orchestration | 0 | 4 |
| Experiment ledger | 0 | 4 |
| Artifact hygiene | 0 | 4 |
| Campaign system | 1 | 4 |
| Data pipeline | 2 | 4 |
| Evaluation rigor | 2 | 4 |
| Scheduler / archive | 0 | 4 |
| Dense search surface | 2 | 4 |
| Reporting | 0 | 4 |
| Reliability / recovery | 1 | 4 |
| Security boundaries | 1 | 3 |
| Testing | 0 | 3 |
| Documentation quality | 1 | 4 |

## Current score

Update this after every phase.

### Phase 0
- Repo knowledge store: 4
- Runner / orchestration: 0
- Experiment ledger: 0
- Artifact hygiene: 0
- Campaign system: 1
- Data pipeline: 2
- Evaluation rigor: 2
- Scheduler / archive: 0
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 1
- Security boundaries: 2
- Testing: 1
- Documentation quality: 4
- Validation note: `bootstrap`, `preflight`, `smoke`, spec lint, and the Phase 0 foundation tests now exist in code.

### Phase 1
- Repo knowledge store: 4
- Runner / orchestration: 2
- Experiment ledger: 2
- Artifact hygiene: 2
- Campaign system: 1
- Data pipeline: 2
- Evaluation rigor: 2
- Scheduler / archive: 0
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 2
- Security boundaries: 2
- Testing: 2
- Documentation quality: 4
- Validation note: fake success/failure runs, SQLite persistence, artifact indexing, `inspect`, and preliminary `score` now exist in code and tests.

### Phase 2
- Repo knowledge store: 4
- Runner / orchestration: 2
- Experiment ledger: 2
- Artifact hygiene: 2
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 2
- Scheduler / archive: 0
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 2
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: `campaign build`/`campaign verify`, deterministic offline packing, and campaign asset integrity checks now exist in code and tests.

### Phase 3
- Repo knowledge store: 4
- Runner / orchestration: 3
- Experiment ledger: 3
- Artifact hygiene: 3
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 1
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 3
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: rule-based `score`, `replay`, source-linked replay proposals, and visible pre-eval checkpoint retention now exist in code and tests.

### Phase 4 (slice 1)
- Repo knowledge store: 4
- Runner / orchestration: 3
- Experiment ledger: 3
- Artifact hygiene: 3
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 2
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 3
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: `run --generate structured` now creates scheduler-selected campaign-local proposals, persists proposal snapshots, and avoids duplicate config fingerprints in code and tests.

### Phase 4 (slice 2)
- Repo knowledge store: 4
- Runner / orchestration: 3
- Experiment ledger: 3
- Artifact hygiene: 3
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 2
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 3
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: campaign archive snapshots are now persisted and inspectable, and `export-code-proposal` writes self-contained code-lane packs for `code_patch` proposals.

### Phase 4 complete
- Repo knowledge store: 4
- Runner / orchestration: 3
- Experiment ledger: 3
- Artifact hygiene: 3
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 3
- Dense search surface: 2
- Reporting: 0
- Reliability / recovery: 3
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: deterministic queue fill, archive snapshots, inspectable campaign state, and self-contained code proposal export are all implemented and covered by tests.

### Phase 5 complete
- Repo knowledge store: 4
- Runner / orchestration: 3
- Experiment ledger: 3
- Artifact hygiene: 3
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 3
- Dense search surface: 3
- Reporting: 0
- Reliability / recovery: 3
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: grouped dense defaults, legality-aware structured mutations, cached backend selection, explicit device profiles, strict compiled Windows GPU smoke, and tiny real campaign smoke assets are now implemented and covered by tests.

### Phase 6 complete
- Repo knowledge store: 4
- Runner / orchestration: 4
- Experiment ledger: 4
- Artifact hygiene: 4
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 3
- Dense search surface: 3
- Reporting: 3
- Reliability / recovery: 4
- Security boundaries: 2
- Testing: 3
- Documentation quality: 4
- Validation note: daily report bundles, campaign-local leaderboards, champion cards, crash summaries, `report`, `night`, latest-report inspection, and fake overnight session coverage are now implemented and covered by tests.

### Phase 7 complete
- Repo knowledge store: 4
- Runner / orchestration: 4
- Experiment ledger: 4
- Artifact hygiene: 4
- Campaign system: 3
- Data pipeline: 3
- Evaluation rigor: 3
- Scheduler / archive: 3
- Dense search surface: 3
- Reporting: 3
- Reliability / recovery: 4
- Security boundaries: 2
- Testing: 4
- Documentation quality: 4
- Validation note: auto-resume from interrupted `running` proposals, conservative cleanup with artifact-index refresh, machine-readable `doctor` diagnostics, resumed-session report notes, dedicated GPU smoke CLI coverage, and code-lane export/import round-trip execution are now implemented and covered by tests.

### Roadmap 8.6 -> 10 signoff snapshot
- Repo knowledge store: 4
- Runner / orchestration: 4
- Experiment ledger: 4
- Artifact hygiene: 4
- Campaign system: 4
- Data pipeline: 3
- Evaluation rigor: 4
- Scheduler / archive: 4
- Dense search surface: 3
- Reporting: 4
- Reliability / recovery: 4
- Security boundaries: 2
- Testing: 4
- Documentation quality: 4
- Validation note: the current repo now includes versioned multi-file migrations, explicit eval-split validation reviews, evidence-traced memory, repeated-dead-end-aware scheduling, runtime autotune, evidence-grounded code packs, showcase automation, and a final lightweight signoff script.

## Exit target for v1

The project reaches “real lab” status when:
- no critical domain is below 3
- documentation quality is 4
- runner, ledger, scheduler, campaigns, and reporting are all at least 3
- the system can survive overnight unattended use

## Notes

If a phase improves only code and not the score, the phase was probably underspecified.
If a score improves, the reason should be obvious from tests, contracts, or operator experience.
