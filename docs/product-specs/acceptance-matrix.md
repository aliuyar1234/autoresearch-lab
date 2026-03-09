# Product acceptance matrix

This matrix summarizes the minimum bar for calling the project a real lab.

| Area | Acceptance bar |
|---|---|
| Baseline parity | `base_2k` campaign reproduces the upstream setup closely enough for apples-to-apples comparison |
| Runner | every run gets manifest, artifacts, terminal summary, and terminal status |
| Ledger | SQLite can reconstruct runs, proposals, promotions, champions, and reports |
| Campaigns | at least `base_2k`, `stories_2k`, and `long_4k` are defined and verifiable |
| Data pipeline | tokenizer, pretokenized shards, and packed blocks are materialized offline with manifests |
| Evaluation | scout/main/confirm lanes and search/audit/locked splits exist where appropriate |
| Scheduler | can generate, queue, select, and promote structured proposals without manual babysitting |
| Archive | champions and representative near-misses are preserved with lineage |
| Code lane | can export a self-sufficient code proposal pack and import the result back into the lab |
| Reports | an overnight run yields a morning report that is actually useful |
| Runtime | backend selection, device profile, compile/perf stats, and VRAM reporting are recorded |
| Reliability | late failures do not erase experiment history; crash classes and cleanup are implemented |
| Tests | unit + integration + GPU smoke coverage exist for core paths |
| Docs | repo-local docs are enough for Codex or a new engineer to navigate the system |

## Full-project signoff checklist

The project may be called complete only when all of the following are true:

- [ ] `python -m lab.cli bootstrap` initializes a clean repo
- [ ] `python -m lab.cli preflight --campaign base_2k` succeeds on the target workstation
- [ ] `python -m lab.cli campaign build --campaign base_2k` materializes assets
- [ ] `python -m lab.cli run --campaign base_2k --generate structured --lane scout` completes and records artifacts
- [ ] `python -m lab.cli night --campaign base_2k --hours 1` can run unattended and generate a report
- [ ] report output clearly identifies winners, failures, and next actions
- [ ] at least one code proposal pack can be exported and round-tripped
- [ ] cleanup can safely prune discardable artifacts
- [ ] GPU smoke test passes on the target machine
- [ ] docs and schemas match implementation reality
