from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import SAMPLE_PROPOSAL, SUCCESS_TARGET, run_cli, target_json_command


class RuntimeAutotuneIntegrationTests(unittest.TestCase):
    def test_autotune_cache_warms_and_runner_applies_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            first_autotune = run_cli(
                "autotune",
                temp_root,
                "--campaign",
                "base_2k",
                "--lane",
                "scout",
                "--json",
            )
            self.assertEqual(first_autotune.returncode, 0, first_autotune.stderr)
            first_payload = json.loads(first_autotune.stdout)
            self.assertTrue(first_payload["ok"])
            self.assertFalse(first_payload["from_cache"])
            self.assertIn("winner", first_payload)
            self.assertTrue(Path(first_payload["cache_path"]).exists())

            second_autotune = run_cli(
                "autotune",
                temp_root,
                "--campaign",
                "base_2k",
                "--lane",
                "scout",
                "--json",
            )
            self.assertEqual(second_autotune.returncode, 0, second_autotune.stderr)
            second_payload = json.loads(second_autotune.stdout)
            self.assertTrue(second_payload["ok"])
            self.assertTrue(second_payload["from_cache"])

            run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(SAMPLE_PROPOSAL),
                "--target-command-json",
                target_json_command(
                    [
                        sys.executable,
                        str(SUCCESS_TARGET),
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
                ),
                "--json",
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertTrue(run_payload["ok"])

            run_root = Path(run_payload["artifact_root"])
            manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
            config = json.loads((run_root / "config.json").read_text(encoding="utf-8"))
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))

            winner_overlay = second_payload["winner"]["runtime_overlay"]
            self.assertEqual(manifest["runtime_overlay"], winner_overlay)
            self.assertEqual(manifest["runtime_effective"], winner_overlay)
            self.assertTrue(manifest["autotune"]["from_cache"])
            self.assertEqual(manifest["autotune"]["cache_key"], second_payload["cache_key"])
            self.assertEqual(config["runtime"]["device_batch_size"], winner_overlay["device_batch_size"])
            self.assertEqual(config["runtime"]["eval_batch_size"], winner_overlay["eval_batch_size"])
            self.assertEqual(config["runtime"]["compile_enabled"], winner_overlay["compile_enabled"])
            self.assertEqual(config["runtime"]["autotune"]["cache_key"], second_payload["cache_key"])
            self.assertEqual(summary["runtime_overlay"], winner_overlay)
            self.assertEqual(summary["runtime_effective"], winner_overlay)
            self.assertEqual(summary["autotune"]["cache_key"], second_payload["cache_key"])

            inspect = run_cli("inspect", temp_root, "--experiment", run_payload["experiment_id"], "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertEqual(
                inspect_payload["runtime_execution"]["runtime_overlay"],
                winner_overlay,
            )
            self.assertEqual(
                inspect_payload["runtime_execution"]["autotune"]["cache_key"],
                second_payload["cache_key"],
            )

            report = run_cli("report", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(report.returncode, 0, report.stderr)
            report_payload = json.loads(report.stdout)
            report_json = json.loads(Path(report_payload["artifact_paths"]["report_json"]).read_text(encoding="utf-8"))
            appendix_row = report_json["appendix"]["run_table"][0]
            self.assertEqual(appendix_row["runtime_overlay"], winner_overlay)
            self.assertEqual(appendix_row["runtime_effective"], winner_overlay)
            self.assertTrue(appendix_row["autotune_cache_hit"])


if __name__ == "__main__":
    unittest.main()
