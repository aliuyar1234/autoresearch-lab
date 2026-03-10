from __future__ import annotations

import json
from pathlib import Path

PLACEHOLDER_TOKENS = [
    "campaign_defined_",
    "local_campaign_baseline",
    "TODO",
    "FIXME",
    "TBD",
]

REQUIRED_FILES = [
    "AGENTS.md",
    "ARCHITECTURE.md",
    "README.md",
    "CODEX_GUARDRAILS.md",
    "docs/runbook.md",
    "docs/product-specs/index.md",
    "docs/product-specs/test-matrix.md",
    "docs/generated/resolved-ambiguities.md",
    "reference_impl/README.md",
    "schemas/campaign.schema.json",
    "schemas/proposal.schema.json",
    "schemas/run_manifest.schema.json",
    "schemas/experiment_record.schema.json",
    "sql/001_ledger.sql",
]

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "artifacts",
    ".worktrees",
    ".mypy_cache",
    ".pytest_cache",
}


def iter_repo_files(repo_root: Path):
    self_path = Path(__file__).resolve()
    for path in repo_root.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.resolve() == self_path:
            continue
        yield path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    problems: list[str] = []

    for rel in REQUIRED_FILES:
        if not (repo_root / rel).exists():
            problems.append(f"missing required file: {rel}")

    for path in iter_repo_files(repo_root):
        if path.suffix.lower() == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                problems.append(f"invalid json: {path.relative_to(repo_root)}: {exc}")

        if path.suffix.lower() in {".md", ".json", ".sql", ".py"}:
            text = path.read_text(encoding="utf-8")
            for token in PLACEHOLDER_TOKENS:
                if token in text:
                    problems.append(f"placeholder token `{token}` found in {path.relative_to(repo_root)}")

    if problems:
        print("SPEC LINT FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("SPEC LINT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
