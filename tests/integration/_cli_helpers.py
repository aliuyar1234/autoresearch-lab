from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PROPOSAL = REPO_ROOT / "tests" / "fixtures" / "contracts" / "sample_proposal.json"
SUCCESS_TARGET = REPO_ROOT / "tests" / "fixtures" / "fake_target_success.py"
FAILURE_TARGET = REPO_ROOT / "tests" / "fixtures" / "fake_target_failure.py"
PHASE6_TARGET = REPO_ROOT / "tests" / "fixtures" / "fake_target_phase6.py"
CODE_PATCH_TARGET = REPO_ROOT / "tests" / "fixtures" / "fake_target_code_patch.py"


def base_lab_args(temp_root: Path) -> list[str]:
    return [
        "--repo-root",
        str(REPO_ROOT),
        "--artifacts-root",
        str(temp_root / "artifacts"),
        "--db-path",
        str(temp_root / "lab.sqlite3"),
        "--worktrees-root",
        str(temp_root / ".worktrees"),
    ]


def run_cli(command: str, temp_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "lab.cli", command, *base_lab_args(temp_root), *extra_args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def target_json_command(parts: list[str]) -> str:
    return json.dumps(parts)
