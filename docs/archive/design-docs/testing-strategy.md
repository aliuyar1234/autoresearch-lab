# Testing strategy

## Testing philosophy

The repo is CUDA-first, but that does not mean every test must require a GPU.

Use layered tests:

### Unit tests
No GPU required.
Cover:
- schema handling
- SQLite queries
- scheduler logic
- scoring rules
- manifest parsing
- packer planning logic
- cleanup logic

### Integration tests
Use fake or tiny targets.
Cover:
- runner lifecycle
- artifact writing
- crash classification
- worktree handling
- report generation

### GPU smoke tests
Require local NVIDIA GPU.
Cover:
- backend selection
- one tiny training run
- one tiny eval
- checkpoint-before-eval path
- structured summary path

## Required smoke command

Provide a command such as:
- `uv run python -m lab.cli smoke --gpu`

This must run quickly and verify the lab core is usable.

## Regression requirement

The lab must have at least one parity-oriented test or checklist for:
- baseline campaign boot
- baseline summary schema
- report generation from a sample run

## Test budget realism

Do not make the default test suite expensive.
Use tiny synthetic fixtures where possible.
Reserve heavier GPU checks for opt-in smoke tests.

## Documentation coupling

If a contract changes:
- update schema
- update tests
- update docs

No silent divergence.
