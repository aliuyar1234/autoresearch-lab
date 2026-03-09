from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.paths import build_paths
from lab.settings import load_settings
from lab.utils import SchemaValidationError, read_json, validate_payload, load_schema


REPO_ROOT = Path(__file__).resolve().parents[2]


class CampaignValidationTests(unittest.TestCase):
    def test_base_campaign_manifest_validates(self) -> None:
        settings = load_settings(repo_root=REPO_ROOT, env={})
        paths = build_paths(settings)
        campaign = load_campaign(paths, "base_2k")
        self.assertEqual(campaign["campaign_id"], "base_2k")

    def test_invalid_campaign_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "campaign.json"
            manifest_path.write_text('{"campaign_id": "broken"}\n', encoding="utf-8")
            payload = read_json(manifest_path)
            with self.assertRaises(SchemaValidationError):
                validate_payload(payload, load_schema(REPO_ROOT / "schemas" / "campaign.schema.json"))


if __name__ == "__main__":
    unittest.main()
