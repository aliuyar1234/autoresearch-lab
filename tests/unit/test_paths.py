from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.paths import build_paths, discover_repo_root, ensure_managed_roots, experiment_root, report_root
from lab.settings import load_settings


def _write_repo_skeleton(repo_root: Path) -> None:
    (repo_root / "docs" / "design-docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "schemas").mkdir(parents=True, exist_ok=True)
    (repo_root / "sql").mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    (repo_root / "docs" / "design-docs" / "index.md").write_text("# docs\n", encoding="utf-8")
    (repo_root / "schemas" / "campaign.schema.json").write_text("{}\n", encoding="utf-8")
    (repo_root / "sql" / "001_ledger.sql").write_text("CREATE TABLE IF NOT EXISTS t(id INTEGER);\n", encoding="utf-8")


class PathTests(unittest.TestCase):
    def test_discover_repo_root_from_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_skeleton(repo_root)
            nested = repo_root / "a" / "b" / "c"
            nested.mkdir(parents=True)

            self.assertEqual(discover_repo_root(nested), repo_root.resolve())

    def test_ensure_managed_roots_creates_expected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_skeleton(repo_root)
            settings = load_settings(repo_root=repo_root, env={})
            paths = build_paths(settings)

            created = ensure_managed_roots(paths)

            self.assertTrue(paths.artifacts_root.exists())
            self.assertTrue(paths.worktrees_root.exists())
            self.assertTrue(paths.cache_root.exists())
            self.assertGreaterEqual(len(created), 1)

    def test_helper_paths_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_skeleton(repo_root)
            paths = build_paths(load_settings(repo_root=repo_root, env={}))

            self.assertEqual(experiment_root(paths, "exp-123"), paths.runs_root / "exp-123")
            self.assertEqual(report_root(paths, "base_2k", "2026-03-09"), paths.reports_root / "2026-03-09" / "base_2k")


if __name__ == "__main__":
    unittest.main()
