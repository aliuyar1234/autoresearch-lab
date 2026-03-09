# Acceptance matrix

| Phase | Must be true before phase is considered complete |
|---|---|
| Phase 0 | bootstrap, preflight JSON, and spec lint succeed; baseline path remains runnable |
| Phase 1 | fake success/failure runs produce ledger rows and artifact trees with terminal status |
| Phase 2 | campaign build is idempotent; verify catches broken assets; offline packer is deterministic |
| Phase 3 | score and replay work; checkpoint-before-eval behavior is visible and tested |
| Phase 4 | scheduler respects family mix, dedupes fingerprints, and maintains archive buckets |
| Phase 5 | dense search space and backend selector are real; tiny GPU smoke can emit summary |
| Phase 6 | night session can run end-to-end and generate a useful report |
| Phase 7 | resume, cleanup, and doctor behavior are safe and documented |
