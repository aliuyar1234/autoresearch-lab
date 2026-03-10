# Code-lane Evidence Contract

Code proposals are research tasks, not detached coding errands.

This contract defines what evidence and validation intent must travel with a code-lane proposal export and with its imported return.

## Export pack requirements

Every exported code proposal pack must include:

- `proposal.json`
- `README.md`
- `acceptance_criteria.md`
- `target_files.txt`
- `return_instructions.md`
- `context/campaign.json`
- `context/parent_runs.json`
- `context/evidence.json`
- `context/validation_targets.json`
- `context/proposal_context.md`

If a current comparator exists, also include:

- `context/best_comparator.json`

If target files are available in the repo snapshot, copy them under:

- `context/files/`

## `evidence.json`

`evidence.json` must make the proposal legible without opening SQLite.

It must contain:

- cited memory records
- why each citation matters
- whether each citation is a precedent or a warning
- parent validated winners, if any
- parent failures or warning cases, if any
- retrieval event identity and query context when available

## `validation_targets.json`

`validation_targets.json` must state how the returned change will be judged.

It must contain:

- primary metric name
- primary metric direction
- expected direction for the proposal
- whether confirm review is required
- whether audit is expected
- whether audit is recommended
- comparator experiment ids when relevant

## README expectations

The exported README must answer:

- what to build
- why now
- what prior evidence exists
- what files may be changed
- how success will be judged after return

## Import lineage requirements

When a patch or worktree is imported, the lab must preserve lineage from:

- evidence
- proposal
- imported diff
- executed run
- final result

At minimum, import metadata must record:

- proposal id
- campaign id
- import timestamp
- return kind
- changed files
- deleted files
- diff stats
- evidence references or paths
- validation-target references or paths

## Run artifact requirements

When a code-lane proposal is executed, the run artifact root must retain the import lineage artifacts so later inspection, reports, and memory ingestion do not depend on ad hoc parsing of proposal notes.

Recommended retained files:

- `code_import/return_manifest.json`
- `code_import/returned.patch`
- `code_import/evidence.json`
- `code_import/validation_targets.json`
- `code_import/proposal_context.md`

## Memory expectations

Code-lane results must become first-class memory records through the same experiment-memory ingestion path as other proposals.

The memory payload should preserve enough code-lane context to answer:

- what files were targeted
- what files were changed or deleted
- what evidence backed the proposal
- what validation intent applied

The code lane is part of the remembering lab.
