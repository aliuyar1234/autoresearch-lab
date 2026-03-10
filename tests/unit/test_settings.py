from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.settings import SettingsError, load_settings


def _write_repo_skeleton(repo_root: Path) -> None:
    (repo_root / "docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "schemas").mkdir(parents=True, exist_ok=True)
    (repo_root / "sql").mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    (repo_root / "README.md").write_text("# tmp\n", encoding="utf-8")
    (repo_root / "docs" / "runbook.md").write_text("# runbook\n", encoding="utf-8")
    (repo_root / "schemas" / "campaign.schema.json").write_text("{}\n", encoding="utf-8")
    (repo_root / "sql" / "001_ledger.sql").write_text("CREATE TABLE IF NOT EXISTS t(id INTEGER);\n", encoding="utf-8")


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_resolve_inside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_skeleton(repo_root)

            settings = load_settings(repo_root=repo_root, env={})

            self.assertEqual(settings.repo_root, repo_root.resolve())
            self.assertEqual(settings.artifacts_root, (repo_root / "artifacts").resolve())
            self.assertEqual(settings.worktrees_root, (repo_root / ".worktrees").resolve())
            self.assertEqual(settings.db_path, (repo_root / "artifacts" / "lab.sqlite3").resolve())

    def test_precedence_is_cli_then_env_then_lab_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_skeleton(repo_root)
            (repo_root / ".lab.env").write_text(
                "LAB_ARTIFACTS_ROOT=env-file-artifacts\nLAB_DB_PATH=env-file.sqlite3\n",
                encoding="utf-8",
            )

            from_env_file = load_settings(repo_root=repo_root, env={})
            self.assertEqual(from_env_file.artifacts_root, (repo_root / "env-file-artifacts").resolve())
            self.assertEqual(from_env_file.db_path, (repo_root / "env-file.sqlite3").resolve())

            from_env = load_settings(
                repo_root=repo_root,
                env={
                    "LAB_ARTIFACTS_ROOT": "env-artifacts",
                    "LAB_DB_PATH": "env.sqlite3",
                },
            )
            self.assertEqual(from_env.artifacts_root, (repo_root / "env-artifacts").resolve())
            self.assertEqual(from_env.db_path, (repo_root / "env.sqlite3").resolve())

            from_cli = load_settings(
                repo_root=repo_root,
                artifacts_root=repo_root / "cli-artifacts",
                db_path=repo_root / "cli.sqlite3",
                env={
                    "LAB_ARTIFACTS_ROOT": "env-artifacts",
                    "LAB_DB_PATH": "env.sqlite3",
                },
            )
            self.assertEqual(from_cli.artifacts_root, (repo_root / "cli-artifacts").resolve())
            self.assertEqual(from_cli.db_path, (repo_root / "cli.sqlite3").resolve())

    def test_missing_repo_markers_raise_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
            with self.assertRaises(SettingsError):
                load_settings(repo_root=repo_root, env={})


if __name__ == "__main__":
    unittest.main()
