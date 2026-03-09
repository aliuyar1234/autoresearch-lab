# Code-lane proposal pack

This document defines the pack exported for external coding agents such as Codex.

The point of the pack is to make the code lane self-sufficient.

## Why this exists

The original upstream concept was mostly “edit `train.py` and run again.”
This lab keeps that spirit but formalizes it.

A code-lane proposal pack should let an external coding agent act without:
- reading chat history
- inferring hidden goals
- free-associating the architecture

## Required contents of an exported pack

1. `proposal.json`
2. `README.md`
3. `acceptance_criteria.md`
4. `target_files.txt`
5. `context/`
6. `return_instructions.md`

## `proposal.json`

Must contain:
- proposal id
- campaign id
- lane
- family
- kind = `code_patch`
- hypothesis
- rationale
- parent ids
- base commit
- target files
- guardrails
- acceptance summary

## `README.md`

Should state:
- what problem is being solved
- what must not change
- how the result will be scored
- how to return the patch

## `acceptance_criteria.md`

Must include:
- functional acceptance criteria
- test expectations
- non-goals
- specific files allowed to change
- forbidden files or directories

## `target_files.txt`

One path per line.
This is the allowlist.

## `context/`

Should include only the minimum relevant context:
- current best comparator summary
- parent run summaries
- excerpts of relevant code
- relevant design docs
- relevant product specs

Do **not** dump the whole repo.
Do **not** include raw crash logs unless they are the direct subject of the proposal.

## `return_instructions.md`

Must define the accepted return formats:
- patch file
- worktree path

It should also state that the result will be executed by the same runner and scored by the same promotion logic.

Current CLI import path supports patch files and worktree paths directly.
If an external agent returns a git commit, convert it to a patch or worktree before import.

## Import rules

Imported code-lane results must still:
- produce a structured summary
- validate against schemas
- be attached to a proposal and experiment lineage
- pass through the same archive and report pipeline

The code lane is not an escape hatch from the lab contracts.
