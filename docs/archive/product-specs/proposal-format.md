# Proposal format

Proposals are the hypotheses the lab can execute.

## Two axes, not one

A proposal has two independent descriptors.

### `family`
Research intent.

Required families:
- `baseline`
- `exploit`
- `ablation`
- `combine`
- `novel`
- `manual`

### `kind`
Implementation mode.

Required kinds:
- `structured`
- `code_patch`
- `manual`

Examples:
- a normal local mutation around a champion: `family=exploit`, `kind=structured`
- an ablation authored by a human: `family=ablation`, `kind=manual`
- a Codex patch implementing a trainer change: `family=exploit` or `novel`, `kind=code_patch`

## Storage

Canonical machine-readable proposal:
- JSON file validating against `schemas/proposal.schema.json`

Recommended working location:
- `artifacts/proposals/`
- optionally committed exemplars under `templates/` or `docs/`

## Required fields

- `proposal_id`
- `campaign_id`
- `lane`
- `family`
- `kind`
- `status`
- `created_at`
- `generator`
- `parent_ids`
- `hypothesis`
- `rationale`
- `config_overrides`
- `complexity_cost`
- `expected_direction`
- `tags`

Optional fields:
- `code_patch`
- `notes`
- `source_experiments`
- `novelty_reason`
- `guardrails`

## Semantics

### `config_overrides`
A nested object applied over campaign/model defaults.

It must be:
- explicit
- deterministic
- small enough to diff/read

### `complexity_cost`
Small integer used as a tie-break signal.
Not a weighted-score replacement.

Suggested scale:
- `0` trivial change
- `1` small config change
- `2` medium complexity
- `3` high-complexity structured change
- `4+` increasingly invasive code edits

### `expected_direction`
Allowed values:
- `improve`
- `neutral`
- `exploratory`

### `generator`
Allowed examples:
- `scheduler`
- `human`
- `codex`
- `imported`

## Code patch extension

For `kind = "code_patch"`, `code_patch` must contain:
- `target_files`
- `base_commit`
- `patch_path` or patch inline reference
- `acceptance_summary`
- optional `worktree_id`

A code proposal pack exported for Codex should include:
- proposal JSON
- concise repo context
- exact allowed file list
- acceptance criteria
- return instructions

See `code-lane-pack.md`.

## Parentage model

`parent_ids` should encode the immediate research ancestry:
- zero parents for a brand-new baseline or manual seed
- one parent for exploit or ablation
- many parents for combine

This ancestry is used by:
- reports
- archive lineage
- scheduler memory

## Promotion/disposition fields

Proposal status is separate from experiment status.

Suggested statuses:
- `queued`
- `running`
- `completed`
- `discarded`
- `promoted`
- `archived`
- `superseded`

## Guardrails

A proposal may optionally include guardrails such as:
- max VRAM budget
- do not modify target depth beyond range
- do not enable unsupported backend
- forbid specific files for code proposals

Guardrails are especially important for code-level proposals.
