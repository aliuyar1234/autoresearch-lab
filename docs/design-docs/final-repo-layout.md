# Final repo layout

The implementation should converge on approximately this layout.

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── CODEX_GUARDRAILS.md
├── docs/
│   ├── DESIGN.md
│   ├── PLANS.md
│   ├── PRODUCT_SENSE.md
│   ├── QUALITY_SCORE.md
│   ├── RELIABILITY.md
│   ├── SECURITY.md
│   ├── design-docs/
│   ├── exec-plans/
│   ├── generated/
│   ├── product-specs/
│   └── references/
├── schemas/
├── sql/
├── templates/
├── tools/
│   └── spec_lint.py
├── reference_impl/
├── lab/
│   ├── __init__.py
│   ├── version.py
│   ├── settings.py
│   ├── paths.py
│   ├── cli.py
│   ├── preflight.py
│   ├── contracts.py
│   ├── runner/
│   ├── ledger/
│   ├── scheduler/
│   ├── campaigns/
│   ├── backends/
│   ├── reports/
│   └── utils/
├── research/
│   └── dense_gpt/
│       ├── __init__.py
│       ├── defaults.py
│       ├── train.py
│       ├── model.py
│       ├── optim.py
│       ├── search_space.py
│       ├── mutation_rules.py
│       └── fingerprint.py
├── campaigns/
│   ├── base_2k/
│   ├── stories_2k/
│   └── long_4k/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── gpu/
│   └── fixtures/
├── artifacts/         # gitignored
├── .worktrees/        # gitignored
└── .lab.env           # local optional config
```

## Directory responsibilities

### `lab/`
Stable operating system for the lab.

### `research/dense_gpt/`
Mutable research substrate.

### `campaigns/`
Human-readable campaign manifests and notes committed to git.

### `schemas/`
Machine-readable contract definitions.

### `sql/`
Ledger schema.

### `templates/`
Boilerplate for new campaigns and reports.

### `reference_impl/`
Concrete reference algorithms to reduce drift.

### `artifacts/`
Local output, never committed.

## File ownership rules

### Infrastructure-owned files
Only change when phase docs or concrete bugs require it:
- `lab/**`
- `schemas/**`
- `sql/**`
- `tools/spec_lint.py`

### Research-owned files
Safe mutation surface:
- `research/dense_gpt/**`

### Human-curated files
- campaign manifests
- design docs
- acceptance criteria
- core beliefs
- resolved ambiguity log

## Migration note

Do not delete the original top-level `prepare.py` / `train.py` path too early.
Preserve baseline parity long enough to compare old and new behavior.
