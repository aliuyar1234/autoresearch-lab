from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import SAMPLE_PROPOSAL, SUCCESS_TARGET, run_cli, target_json_command


class MemoryBackfillIntegrationTests(unittest.TestCase):
    def test_memory_backfill_is_idempotent_and_inspectable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

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

            report = run_cli("report", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(report.returncode, 0, report.stderr)

            first = run_cli("memory", temp_root, "backfill", "--campaign", "base_2k", "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            first_payload = json.loads(first.stdout)
            self.assertGreater(first_payload["memory_created"] + first_payload["memory_skipped_existing"], 0)

            second = run_cli("memory", temp_root, "backfill", "--campaign", "base_2k", "--json")
            self.assertEqual(second.returncode, 0, second.stderr)
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["memory_created"], 0)
            self.assertGreater(second_payload["memory_skipped_existing"], 0)

            inspect = run_cli("memory", temp_root, "inspect", "--campaign", "base_2k", "--limit", "10", "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertGreater(inspect_payload["count"], 0)


if __name__ == "__main__":
    unittest.main()
