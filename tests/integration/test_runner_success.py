from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import SAMPLE_PROPOSAL, SUCCESS_TARGET, run_cli, target_json_command


class RunnerSuccessTests(unittest.TestCase):
    def test_successful_run_creates_db_rows_and_artifacts(self) -> None:
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
            payload = json.loads(run.stdout)
            self.assertTrue(payload["ok"])

            experiment_id = payload["experiment_id"]
            run_root = temp_root / "artifacts" / "runs" / experiment_id
            for name in (
                "manifest.json",
                "proposal.json",
                "config.json",
                "env.json",
                "stdout.log",
                "stderr.log",
                "summary.json",
                "artifact_index.json",
            ):
                self.assertTrue((run_root / name).exists(), name)

            connection = sqlite3.connect(temp_root / "lab.sqlite3")
            try:
                experiment_count = connection.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
                proposal_count = connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(experiment_count, 1)
            self.assertEqual(proposal_count, 1)

            inspect = run_cli("inspect", temp_root, "--experiment", experiment_id, "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertEqual(inspect_payload["status"], "completed")

            score = run_cli("score", temp_root, "--experiment", experiment_id, "--json")
            self.assertEqual(score.returncode, 0, score.stderr)
            score_payload = json.loads(score.stdout)
            self.assertAlmostEqual(score_payload["primary_metric_value"], 0.97, places=6)


if __name__ == "__main__":
    unittest.main()
