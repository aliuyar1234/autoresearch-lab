# Runbook

This runbook is the operator guide for Autoresearch Lab.

## 1. Bootstrap a fresh clone

```bash
git clone https://github.com/aliuyar1234/autoresearch.git autoresearch-lab
cd autoresearch-lab
git remote add upstream https://github.com/karpathy/autoresearch.git
git fetch upstream
```

Copy the overlay from this pack into the repo root, then:

```bash
uv sync
python -m lab.cli bootstrap
python -m lab.cli preflight --campaign base_2k --benchmark-backends
python -m lab.cli smoke --gpu
python -m lab.cli doctor
python tools/spec_lint.py
```

Expected outcome:
- managed roots created
- SQLite initialized
- machine/environment summary printed
- Windows venv includes `triton-windows` so `torch.compile` is available in the repo env
- `smoke --gpu` builds tiny real campaign assets under `artifacts/smoke/` when needed
- `doctor` reports no retained-artifact or DB-integrity errors
- spec lint passes

## 2. Verify baseline before major refactor

If the baseline path still exists:

```bash
uv run prepare.py
uv run train.py
```

Goal:
- confirm the workstation and dependencies are healthy
- establish confidence before deeper migration

## 3. Build campaign assets

```bash
python -m lab.cli campaign list
python -m lab.cli campaign build --campaign base_2k
python -m lab.cli campaign verify --campaign base_2k
```

Expected outputs:
- tokenizer assets
- pretokenized shards
- packed blocks
- integrity manifests

## 4. Run one structured scout experiment

```bash
python -m lab.cli run --campaign base_2k --generate structured --lane scout
```

Look for:
- experiment id
- proposal family and kind
- resolved `config.json` under the run artifact root
- artifact path
- terminal summary status
- primary metric in summary

## 5. Run a bounded overnight session

```bash
python -m lab.cli night --campaign base_2k --hours 8 --allow-confirm
```

Expected outputs:
- multiple experiment artifact directories
- updated SQLite ledger
- auto-resume of any proposals left in `running` state from a previous interrupted session
- morning report bundle under `artifacts/reports/<date>/<campaign_id>/`

## 5a. Preview or fill the structured queue

```bash
python -m lab.cli campaign queue --campaign base_2k --count 5
python -m lab.cli campaign queue --campaign base_2k --count 5 --apply
```

Look for:
- deterministic lane/family mix
- no duplicate config fingerprints
- queued proposals visible from `inspect --campaign`

## 6. Inspect results

```bash
python -m lab.cli inspect --campaign base_2k
python -m lab.cli inspect --experiment <experiment_id>
python -m lab.cli report --campaign base_2k
```

Look for:
- archive buckets and current campaign state
- top candidates
- failure summary
- recommended next actions
- latest report, leaderboard, and champion-card artifact paths

## 7. Export a code proposal pack

Use this only when structured search is not enough.

```bash
python -m lab.cli export-code-proposal --proposal-id <proposal_id>
```

Current implementation expects a proposal whose `kind` is `code_patch`.

The pack should include:
- proposal json
- target file list
- base commit
- acceptance criteria
- concise context
- return instructions

Return path:
- a returned patch or worktree is imported and run through the same runner and scoring path

Import a returned patch or worktree:

```bash
python -m lab.cli import-code-proposal --proposal-id <proposal_id> --patch-path path\\to\\returned.patch
```

or

```bash
python -m lab.cli import-code-proposal --proposal-id <proposal_id> --worktree-path path\\to\\returned_worktree
```

Then execute it through the same runner:

```bash
python -m lab.cli run --proposal-id <proposal_id>
```

Current implementation imports patch files and worktree paths directly. Git-commit returns should be converted to a patch or worktree before import.

## 8. Diagnose common failures

### Preflight failure
Action:
- rerun `preflight --json`
- run `doctor --json`
- optionally rerun `preflight --benchmark-backends --campaign <id>`
- fix missing assets or environment issues before queueing more runs

### OOM during training
Action:
- inspect device batch, sequence length, backend, and compile path
- scheduler should down-rank similar proposals automatically

### OOM during eval
Action:
- confirm pre-eval checkpoint exists
- rerun in confirm lane only if recovery path is defined

### Import/compile failure
Action:
- inspect worktree diff or recent code proposal
- retain crash exemplar for report and debugging

## 9. Cleanup

Always start with dry-run:

```bash
python -m lab.cli cleanup --dry-run
```

Then apply if the plan looks safe:

```bash
python -m lab.cli cleanup --apply
```

The cleanup command must never delete:
- champion artifacts
- promoted artifacts
- reports
- campaign assets
- any path outside managed roots
- crash exemplars for failed runs

Current implementation prunes only `discardable` / `ephemeral` artifacts and refreshes `artifact_index.json` for touched runs.

## 10. Resume after interruption

Preferred flow:
- rerun `python -m lab.cli night ...`
- lab reconstructs queue/session state from SQLite + artifacts
- partial progress remains visible in the next report
- the next report includes session notes describing recovered or interrupted state

Manual diagnostics:

```bash
python -m lab.cli doctor --json
```

Look for:
- `missing_artifact`
- `missing_report_artifact`
- `proposal_still_running`
- DB integrity errors

## 11. Add a new structured knob

Checklist:
1. add the knob to `research/dense_gpt/defaults.py`
2. expose it in `research/dense_gpt/search_space.py`
3. ensure `mutation_rules.py` can mutate it sanely
4. include it in config fingerprinting
5. update relevant tests
6. update docs if the knob becomes an important public concept

## 12. Add a new campaign

Checklist:
1. copy a template from `templates/`
2. create `campaigns/<id>/campaign.json`
3. create `campaigns/<id>/README.md`
4. implement or extend builder under `lab/campaigns/builders/`
5. run `campaign verify`
6. do not mix leaderboards across incomparable campaigns

## 13. Merge readiness checklist

Before calling the lab “impressive”:
- baseline parity path exists for `base_2k`
- fake/integration tests pass
- GPU smoke passes
- overnight mini-session passes
- `doctor` returns clean output for the repo env
- docs/specs/schemas are aligned
- report is clear enough that a human would actually trust it
