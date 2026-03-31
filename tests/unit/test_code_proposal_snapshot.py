from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lab.code_proposals import prepare_code_patch_execution
from lab.paths import build_paths, ensure_managed_roots
from lab.settings import load_settings


def _write_repo_skeleton(repo_root: Path) -> None:
    (repo_root / "docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "schemas").mkdir(parents=True, exist_ok=True)
    (repo_root / "sql").mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    (repo_root / "README.md").write_text("# tmp\n", encoding="utf-8")
    (repo_root / "docs" / "runbook.md").write_text("# runbook\n", encoding="utf-8")
    (repo_root / "schemas" / "campaign.schema.json").write_text("{}\n", encoding="utf-8")
    (repo_root / "sql" / "001_ledger.sql").write_text("CREATE TABLE IF NOT EXISTS t(id INTEGER);\n", encoding="utf-8")


class CodeProposalSnapshotTests(unittest.TestCase):
    def test_prepare_code_patch_execution_skips_source_managed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            source_repo = temp_root / "source_repo"
            runtime_root = temp_root / "runtime_workspace"
            _write_repo_skeleton(source_repo)

            (source_repo / "train.py").write_text("print('hello')\n", encoding="utf-8")
            (source_repo / "notes.txt").write_text("keep me\n", encoding="utf-8")
            (source_repo / ".lab.env").write_text(
                "\n".join(
                    [
                        "LAB_ARTIFACTS_ROOT=state/artifacts",
                        "LAB_WORKTREES_ROOT=state/worktrees",
                        "LAB_CACHE_ROOT=state/cache",
                        "LAB_DB_PATH=state/lab.sqlite3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            (source_repo / "state" / "artifacts" / "runs" / "exp_old").mkdir(parents=True, exist_ok=True)
            (source_repo / "state" / "artifacts" / "runs" / "exp_old" / "payload.txt").write_text("artifact\n", encoding="utf-8")
            (source_repo / "state" / "worktrees" / "exp_old" / "repo").mkdir(parents=True, exist_ok=True)
            (source_repo / "state" / "worktrees" / "exp_old" / "repo" / "ghost.txt").write_text("worktree\n", encoding="utf-8")
            (source_repo / "state" / "cache").mkdir(parents=True, exist_ok=True)
            (source_repo / "state" / "cache" / "cache.bin").write_text("cache\n", encoding="utf-8")
            (source_repo / "state" / "lab.sqlite3").write_text("db\n", encoding="utf-8")

            settings = load_settings(
                repo_root=source_repo,
                artifacts_root=runtime_root / "artifacts",
                worktrees_root=runtime_root / ".worktrees",
                cache_root=runtime_root / "cache",
                db_path=runtime_root / "lab.sqlite3",
                env={},
            )
            paths = build_paths(settings)
            ensure_managed_roots(paths)

            import_root = runtime_root / "imports" / "demo"
            import_root.mkdir(parents=True, exist_ok=True)
            (import_root / "return_manifest.json").write_text(
                json.dumps(
                    {
                        "return_kind": "worktree",
                        "changed_files": [],
                        "deleted_files": [],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            proposal = {
                "kind": "code_patch",
                "code_patch": {
                    "import_root": str(import_root),
                    "patch_path": "unused.patch",
                },
            }

            prepared = prepare_code_patch_execution(paths, proposal, experiment_id="exp_snapshot")
            execution_root = Path(prepared["execution_root"])

            self.assertTrue((execution_root / "train.py").exists())
            self.assertTrue((execution_root / "notes.txt").exists())
            self.assertFalse((execution_root / "state" / "artifacts").exists())
            self.assertFalse((execution_root / "state" / "worktrees").exists())
            self.assertFalse((execution_root / "state" / "cache").exists())
            self.assertFalse((execution_root / "state" / "lab.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
