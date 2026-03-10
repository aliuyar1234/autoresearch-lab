from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lab.paths import build_paths, ensure_managed_roots
from lab.settings import load_settings
from research.dense_gpt.train import _load_blocks


REPO_ROOT = Path(__file__).resolve().parents[2]


class EvalSplitContractTests(unittest.TestCase):
    def test_load_blocks_uses_only_requested_eval_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                cache_root=temp_root / "cache",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            ensure_managed_roots(paths)

            asset_root = temp_root / "packed_assets"
            asset_root.mkdir(parents=True, exist_ok=True)
            (asset_root / "train.json").write_text(json.dumps([{"tokens": [10, 11, 12, 13]}]), encoding="utf-8")
            (asset_root / "search.json").write_text(json.dumps([{"tokens": [20, 21, 22, 23]}]), encoding="utf-8")
            (asset_root / "audit.json").write_text(json.dumps([{"tokens": [30, 31, 32, 33]}]), encoding="utf-8")
            (asset_root / "locked.json").write_text(json.dumps([{"tokens": [40, 41, 42, 43]}]), encoding="utf-8")
            (asset_root / "packed_manifest.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {"split": "train", "path": "train.json"},
                            {"split": "search_val", "path": "search.json"},
                            {"split": "audit_val", "path": "audit.json"},
                            {"split": "locked_val", "path": "locked.json"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            campaign = {
                "assets": {
                    "root": str(asset_root),
                    "packed_manifest": "packed_manifest.json",
                }
            }

            train_blocks, audit_blocks = _load_blocks(paths, campaign, eval_split="audit_val", tiny=False)
            _, search_blocks = _load_blocks(paths, campaign, eval_split="search_val", tiny=False)
            _, locked_blocks = _load_blocks(paths, campaign, eval_split="locked_val", tiny=False)

            self.assertEqual(train_blocks, [[10, 11, 12, 13]])
            self.assertEqual(audit_blocks, [[30, 31, 32, 33]])
            self.assertEqual(search_blocks, [[20, 21, 22, 23]])
            self.assertEqual(locked_blocks, [[40, 41, 42, 43]])


if __name__ == "__main__":
    unittest.main()
