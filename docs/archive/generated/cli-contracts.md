# CLI contracts summary

Top-level command groups:

- `bootstrap`
- `preflight`
- `campaign`
- `run`
- `night`
- `report`
- `inspect`
- `replay`
- `export-code-proposal`
- `import-code-proposal`
- `score`
- `cleanup`
- `smoke`
- `doctor`

Important reminders:

- `preflight --benchmark-backends --campaign <id>` reruns backend selection microbench and refreshes cache state
- `run --generate structured` generates a structured proposal, but that proposal still needs a research `family`
- generated structured runs require `--campaign` and `--lane`; `--family` is optional and otherwise selected by the scheduler
- the default `run` target now uses `research.dense_gpt.train` with a resolved `config.json` snapshot unless a custom target command is supplied
- `campaign queue --campaign <id> --count N [--apply]` previews or persists deterministic structured queue fill
- `inspect --campaign <id>` surfaces campaign-local archive buckets and the latest report bundle when available
- `export-code-proposal --proposal-id <id>` exports a self-contained pack for `code_patch` proposals
- `import-code-proposal --proposal-id <id> --patch-path <path>` or `--worktree-path <path>` imports a returned code-lane result and makes it runnable through the normal runner
- `report --campaign <id>` writes `report.md`/`report.json` plus leaderboard, champion-card, and crash-summary companions, including session notes when a night session was resumed or interrupted
- `night --campaign <id>` now auto-resumes orphaned `running` proposals, runs a bounded unattended loop, and emits a final report bundle
- `cleanup [--dry-run|--apply]` only prunes `discardable` / `ephemeral` artifacts and refreshes per-run artifact indexes
- `smoke --gpu` now benchmarks backends and runs a tiny real dense train/eval path
- `doctor [--campaign <id>]` checks SQLite integrity, retained artifact presence, report files, running proposals, and worktree health
- CLI default output is human-readable
- `--json` output must be stable and machine-consumable
- exit code `6` means interrupted or partial

See `docs/product-specs/lab-cli.md` for the canonical contract.
