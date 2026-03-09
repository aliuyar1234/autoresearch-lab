from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import FAILURE_TARGET, SAMPLE_PROPOSAL, run_cli, target_json_command


class RunnerFailureTests(unittest.TestCase):
    def test_failed_run_records_crash_class_and_logs(self) -> None:
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
                target_json_command([sys.executable, str(FAILURE_TARGET), "--kind", "oom_train"]),
                "--json",
            )
            self.assertEqual(run.returncode, 4, run.stderr)
            payload = json.loads(run.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["crash_class"], "oom_train")

            experiment_id = payload["experiment_id"]
            run_root = temp_root / "artifacts" / "runs" / experiment_id
            self.assertTrue((run_root / "manifest.json").exists())
            self.assertTrue((run_root / "stderr.log").exists())
            self.assertTrue((run_root / "summary.json").exists())

            inspect = run_cli("inspect", temp_root, "--experiment", experiment_id, "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertEqual(inspect_payload["crash_class"], "oom_train")

            connection = sqlite3.connect(temp_root / "lab.sqlite3")
            try:
                status, crash_class = connection.execute(
                    "SELECT status, crash_class FROM experiments WHERE experiment_id = ?",
                    (experiment_id,),
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(status, "failed")
            self.assertEqual(crash_class, "oom_train")

    def test_schema_validation_failure_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            invalid_target = temp_root / "invalid_target.py"
            invalid_target.write_text(
                "\n".join(
                    [
                        "import argparse, json",
                        "from pathlib import Path",
                        "parser = argparse.ArgumentParser()",
                        "parser.add_argument('--summary-out', required=True)",
                        "parser.add_argument('--experiment-id', required=True)",
                        "parser.add_argument('--proposal-id', required=True)",
                        "parser.add_argument('--campaign-id', required=True)",
                        "parser.add_argument('--lane', required=True)",
                        "args = parser.parse_args()",
                        "Path(args.summary_out).write_text(json.dumps({",
                        "  'experiment_id': args.experiment_id,",
                        "  'proposal_id': args.proposal_id,",
                        "  'campaign_id': args.campaign_id,",
                        "  'lane': args.lane,",
                        "  'status': 'completed'",
                        "}), encoding='utf-8')",
                    ]
                ),
                encoding="utf-8",
            )

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
                        str(invalid_target),
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
                    ]
                ),
                "--json",
            )
            self.assertEqual(run.returncode, 5, run.stderr)
            payload = json.loads(run.stdout)
            self.assertTrue(payload["schema_failed"])
            self.assertEqual(payload["status"], "failed")


if __name__ == "__main__":
    unittest.main()
