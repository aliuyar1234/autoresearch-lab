from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from lab.paths import build_paths, ensure_managed_roots
from lab.settings import load_settings
from lab.smoke_assets import build_smoke_source_documents, ensure_smoke_campaign_assets


REPO_ROOT = Path(__file__).resolve().parents[2]


class SmokeAssetTests(unittest.TestCase):
    def test_base_like_smoke_documents_cover_required_splits(self) -> None:
        from lab.campaigns import load_campaign

        settings = load_settings(repo_root=REPO_ROOT, env={})
        campaign = load_campaign(build_paths(settings), "base_2k")
        documents = build_smoke_source_documents(campaign)
        self.assertIn("smoke_train_00001.txt", documents)
        self.assertIn("shard_06540.parquet", documents)
        self.assertIn("shard_06541.parquet", documents)
        self.assertIn("shard_06542.parquet", documents)

    def test_stories_smoke_documents_land_in_all_splits(self) -> None:
        from lab.campaigns import load_campaign

        settings = load_settings(repo_root=REPO_ROOT, env={})
        campaign = load_campaign(build_paths(settings), "stories_2k")
        documents = build_smoke_source_documents(campaign)
        builder = importlib.import_module(campaign["dataset"]["builder"])
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir)
            for name, text in documents.items():
                (source_root / name).write_text(text, encoding="utf-8")
            splits = builder.collect_split_documents(source_root, campaign)
        self.assertTrue(splits["train"])
        self.assertTrue(splits["search_val"])
        self.assertTrue(splits["audit_val"])
        self.assertTrue(splits["locked_val"])

    def test_ensure_smoke_campaign_assets_builds_verifiable_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            ensure_managed_roots(paths)
            payload = ensure_smoke_campaign_assets(paths, "base_2k")
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["built"])


if __name__ == "__main__":
    unittest.main()
