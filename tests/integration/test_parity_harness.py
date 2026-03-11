from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PARITY_SCRIPT = REPO_ROOT / "tools" / "parity_harness.py"


class ParityHarnessIntegrationTests(unittest.TestCase):
    def test_static_parity_report_is_honest_about_aligned_and_different_parts(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PARITY_SCRIPT), "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["campaign_id"], "base_2k")

        checks = {entry["name"]: entry for entry in payload["checks"]}
        self.assertEqual(checks["sequence_length"]["status"], "aligned")
        self.assertEqual(checks["fixed_budget"]["status"], "aligned")
        self.assertEqual(checks["dataset_contract"]["status"], "documented_difference")
        self.assertEqual(checks["tokenizer_contract"]["status"], "documented_difference")
        self.assertEqual(
            payload["baseline_role"]["lab_native_train_py"],
            "primary structured-search engine for normal lab runs",
        )

    def test_summary_comparison_mode_reports_alignment_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            upstream_summary = temp_root / "upstream_summary.json"
            lab_summary = temp_root / "lab_summary.json"
            upstream_summary.write_text(
                json.dumps(
                    {
                        "metric_name": "val_bpb",
                        "val_bpb": 10.5,
                        "time_budget_seconds": 300,
                    }
                ),
                encoding="utf-8",
            )
            lab_summary.write_text(
                json.dumps(
                    {
                        "primary_metric_name": "val_bpb",
                        "primary_metric_value": 10.2,
                        "budget_seconds": 300,
                        "eval_split": "search_val",
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PARITY_SCRIPT),
                    "--upstream-summary",
                    str(upstream_summary),
                    "--lab-summary",
                    str(lab_summary),
                    "--json",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            comparison = payload["summary_comparison"]
            self.assertTrue(comparison["metric_name_alignment"])
            self.assertTrue(comparison["budget_alignment"])
            self.assertEqual(comparison["lab"]["eval_split"], "search_val")


if __name__ == "__main__":
    unittest.main()
