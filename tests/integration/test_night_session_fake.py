from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import PHASE6_TARGET, missing_preflight_imports, run_cli, target_json_command


def _phase6_target_command() -> str:
    return target_json_command(
        [
            sys.executable,
            str(PHASE6_TARGET),
            "--summary-out",
            "{summary_out}",
            "--experiment-id",
            "{experiment_id}",
            "--proposal-id",
            "{proposal_id}",
            "--campaign-id",
            "{campaign_id}",
            "--lane",
            "{lane}",
            "--backend",
            "{backend}",
            "--device-profile",
            "{device_profile}",
        ]
    )


def _write_base_source_docs(source_root: Path) -> None:
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


@unittest.skipIf(
    bool(missing_preflight_imports()),
    f"night integration requires preflight imports: {', '.join(missing_preflight_imports())}",
)
class NightSessionFakeTests(unittest.TestCase):
    def test_night_session_fake(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            source_root = temp_root / "raw"
            _write_base_source_docs(source_root)
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

            night = run_cli(
                "night",
                temp_root,
                "--campaign",
                "base_2k",
                "--hours",
                "0.01",
                "--max-runs",
                "2",
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(night.returncode, 0, night.stderr)
            payload = json.loads(night.stdout)
            self.assertTrue(payload["ok"])
            self.assertGreaterEqual(payload["run_count"], 1)
            self.assertTrue(Path(payload["report"]["artifact_paths"]["report_json"]).exists())

            inspect = run_cli("inspect", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertIn("latest_report", inspect_payload)
            self.assertTrue(inspect_payload["latest_report"]["report_json_path"])


if __name__ == "__main__":
    unittest.main()
