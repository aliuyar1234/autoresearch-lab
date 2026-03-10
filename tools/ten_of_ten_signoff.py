from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_LINT_SCRIPT = Path("tools") / ("spec_lint" + ".py")
SELECTED_TESTS = [
    "tests/unit/ledger/test_multi_file_migrations.py",
    "tests/integration/test_eval_split_contract.py",
    "tests/integration/test_confirm_promotion_requires_review.py",
    "tests/integration/test_memory_backfill_from_existing_ledger.py",
    "tests/integration/test_autotune_runtime_override.py",
    "tests/integration/test_code_proposal_export_includes_evidence.py",
    "tests/integration/test_showcase_compare_json_scaffold.py",
]


def _run_command(*, label: str, command: list[str], cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "label": label,
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _base_lab_args(temp_root: Path) -> list[str]:
    return [
        "--repo-root",
        str(REPO_ROOT),
        "--artifacts-root",
        str(temp_root / "artifacts"),
        "--db-path",
        str(temp_root / "lab.sqlite3"),
        "--worktrees-root",
        str(temp_root / ".worktrees"),
        "--cache-root",
        str(temp_root / "cache"),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the lightweight 10/10 signoff checks.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--skip-tests", action="store_true", help="skip the curated pytest subset")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else os.pathsep.join([str(REPO_ROOT), existing_pythonpath])

    steps: list[dict[str, Any]] = []
    steps.append(
        _run_command(
            label="spec_lint",
            command=[sys.executable, str(SPEC_LINT_SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        cli_prefix = [sys.executable, "-m", "lab.cli"]
        cli_common = _base_lab_args(temp_root)
        steps.append(
            _run_command(
                label="bootstrap",
                command=[*cli_prefix, "bootstrap", *cli_common, "--json"],
                cwd=REPO_ROOT,
                env=env,
            )
        )
        steps.append(
            _run_command(
                label="campaign_show",
                command=[*cli_prefix, "campaign", *cli_common, "show", "--campaign", "base_2k", "--json"],
                cwd=REPO_ROOT,
                env=env,
            )
        )
        steps.append(
            _run_command(
                label="doctor",
                command=[*cli_prefix, "doctor", *cli_common, "--json"],
                cwd=REPO_ROOT,
                env=env,
            )
        )
        steps.append(
            _run_command(
                label="report_dry_run",
                command=[*cli_prefix, "report", *cli_common, "--campaign", "base_2k", "--json"],
                cwd=REPO_ROOT,
                env=env,
            )
        )

    if not args.skip_tests:
        steps.append(
            _run_command(
                label="selected_tests",
                command=[sys.executable, "-m", "pytest", "-q", *SELECTED_TESTS],
                cwd=REPO_ROOT,
                env=env,
            )
        )

    ok = all(step["ok"] for step in steps)
    payload = {
        "ok": ok,
        "repo_root": str(REPO_ROOT),
        "steps": [
            {
                "label": step["label"],
                "command": step["command"],
                "returncode": step["returncode"],
                "ok": step["ok"],
            }
            for step in steps
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Ten of Ten signoff")
        print(f"Repo root: {REPO_ROOT}")
        for step in steps:
            status = "ok" if step["ok"] else "failed"
            print(f"- {step['label']}: {status}")
            if not step["ok"] and step["stderr"]:
                print(step["stderr"].rstrip())
        print("")
        print("overall: ok" if ok else "overall: failed")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
