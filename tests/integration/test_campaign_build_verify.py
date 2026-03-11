from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import run_cli


class CampaignBuildVerifyTests(unittest.TestCase):
    def _write_base_source_docs(self, source_root: Path) -> None:
        source_root.mkdir(parents=True, exist_ok=True)
        docs = {
            "shard_00001.parquet": "train example one",
            "shard_00002.parquet": "train example two",
            "shard_06540.parquet": "locked validation",
            "shard_06541.parquet": "audit validation",
            "shard_06542.parquet": "search validation",
        }
        for name, text in docs.items():
            (source_root / name).write_text(text, encoding="utf-8")

    def test_campaign_build_is_idempotent_and_verify_catches_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            source_root = temp_root / "raw"
            self._write_base_source_docs(source_root)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            build = run_cli(
                "campaign",
                temp_root,
                "build",
                "--campaign",
                "base_2k",
                "--source-dir",
                str(source_root),
                "--json",
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            build_payload = json.loads(build.stdout)
            self.assertTrue(build_payload["ok"])

            asset_root = temp_root / "artifacts" / "cache" / "campaigns" / "base_2k"
            raw_manifest = json.loads((asset_root / "raw.manifest.json").read_text(encoding="utf-8"))
            tokenizer_manifest = json.loads((asset_root / "tokenizer.manifest.json").read_text(encoding="utf-8"))
            tokenizer_meta = json.loads((asset_root / "tokenizer.meta.json").read_text(encoding="utf-8"))

            self.assertEqual(raw_manifest["source_format"], "utf8_text_files")
            self.assertEqual(tokenizer_manifest["tokenizer_kind"], "byte_fallback")
            self.assertEqual(tokenizer_meta["kind"], "byte_fallback")

            packed_manifest_path = temp_root / "artifacts" / "cache" / "campaigns" / "base_2k" / "packed.manifest.json"
            first_manifest = packed_manifest_path.read_text(encoding="utf-8")

            build_again = run_cli(
                "campaign",
                temp_root,
                "build",
                "--campaign",
                "base_2k",
                "--source-dir",
                str(source_root),
                "--json",
            )
            self.assertEqual(build_again.returncode, 0, build_again.stderr)
            self.assertEqual(first_manifest, packed_manifest_path.read_text(encoding="utf-8"))

            verify = run_cli("campaign", temp_root, "verify", "--campaign", "base_2k", "--json")
            self.assertEqual(verify.returncode, 0, verify.stderr)
            verify_payload = json.loads(verify.stdout)
            self.assertTrue(verify_payload["ok"])

            packed_train = temp_root / "artifacts" / "cache" / "campaigns" / "base_2k" / "packed_train.json"
            packed_train.write_text(packed_train.read_text(encoding="utf-8") + "\ncorruption", encoding="utf-8")

            verify_broken = run_cli("campaign", temp_root, "verify", "--campaign", "base_2k", "--json")
            self.assertEqual(verify_broken.returncode, 3, verify_broken.stderr)
            broken_payload = json.loads(verify_broken.stdout)
            self.assertFalse(broken_payload["ok"])
            self.assertTrue(broken_payload["problems"])


if __name__ == "__main__":
    unittest.main()
