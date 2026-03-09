# System architecture

## Main subsystems

### 1. CLI (`lab.cli`)
User entry point.

Responsibilities:
- bootstrap
- preflight
- build/verify campaign assets
- queue or run proposals
- generate reports
- cleanup / garbage collection
- replay and inspect runs

### 2. Runner (`lab.runner`)
Executes experiments deterministically.

Responsibilities:
- create experiment id
- prepare working directory
- capture environment
- run subprocess
- capture logs
- checkpoint before eval
- classify failure
- write terminal summary

### 3. Ledger (`lab.ledger`)
SQLite-backed metadata store.

Responsibilities:
- persist campaigns, proposals, experiments, artifacts, champions, reports
- support queries for reports and scheduler
- reconstruct state after restart

### 4. Scheduler (`lab.scheduler`)
Chooses what to run next.

Responsibilities:
- manage proposal queue
- balance exploit / ablation / combine / novel / code paths
- promote candidates between budget lanes
- maintain elite archive
- generate next actions

### 5. Campaigns (`lab.campaigns`)
Own data, tokenizer, and eval definitions.

Responsibilities:
- build or verify assets
- define budgets
- define metrics
- define qualitative probes
- define comparability boundaries

### 6. Research surface (`research/dense_gpt`)
Own experimental model/training logic.

Responsibilities:
- structured configs
- model variants
- optimizer and schedule variants
- training entry point
- machine-readable run summary

### 7. Reports (`lab.reports`)
Turn ledger + artifacts into useful outputs.

Responsibilities:
- daily report
- leaderboard
- champion cards
- crash summary
- next-steps recommendations

## Control flow for a structured run

```text
user -> lab.cli run/night
     -> preflight
     -> scheduler selects or generates proposal
     -> runner creates experiment + artifacts
     -> research surface executes
     -> structured summary emitted
     -> ledger updated
     -> scorer decides disposition
     -> archive/promote/report
```

## Control flow for a code proposal run

```text
user/scheduler -> export code proposal pack
               -> isolated worktree
               -> external coding agent edits
               -> local commit/patch recorded
               -> lab runner executes as normal
               -> scorer/archive/report path is identical
```

## Architectural invariants

- runner decisions use structured data
- campaign manifests are explicit
- experiment ids are created before execution
- artifacts are append-only per experiment
- stable infrastructure and mutable research surface are separated
- mainline repo remains clean during proposal execution
- proposals persist both `family` and `kind`

## Why SQLite

SQLite is the right choice here because:
- local
- zero service dependency
- durable
- inspectable
- easy to query
- sufficient for one-user, one-machine operation

Anything bigger is premature.

## Why worktrees

Worktrees provide:
- clean isolation
- reproducible patch provenance
- easier cleanup
- simpler replays
- less branch dirtiness

## Why reports over dashboards

The user wants an answer in the morning, not a platform to administrate.
Static Markdown/HTML reports are enough for v1 and likely better.
