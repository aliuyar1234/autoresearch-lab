from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import PHASE6_TARGET, SAMPLE_PROPOSAL, missing_preflight_imports, run_cli, target_json_command


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


def _assert_envelope(test_case: unittest.TestCase, payload: dict[str, object], command: str) -> None:
    test_case.assertIn("ok", payload)
    test_case.assertEqual(payload["command"], command)
    test_case.assertIn("status", payload)
    test_case.assertIn("message", payload)


class CliOutputContractTests(unittest.TestCase):
    def test_common_path_json_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
            bootstrap_payload = json.loads(bootstrap.stdout)
            _assert_envelope(self, bootstrap_payload, "bootstrap")

            run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(SAMPLE_PROPOSAL),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = json.loads(run.stdout)
            _assert_envelope(self, run_payload, "run")
            self.assertIn("disposition", run_payload)
            self.assertIn("validation_state", run_payload)

            report = run_cli("report", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(report.returncode, 0, report.stderr)
            report_payload = json.loads(report.stdout)
            _assert_envelope(self, report_payload, "report")
            self.assertIn("report_path", report_payload)

            doctor = run_cli("doctor", temp_root, "--json")
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            doctor_payload = json.loads(doctor.stdout)
            _assert_envelope(self, doctor_payload, "doctor")

            cleanup = run_cli("cleanup", temp_root, "--dry-run", "--json")
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            cleanup_payload = json.loads(cleanup.stdout)
            _assert_envelope(self, cleanup_payload, "cleanup")
            self.assertIn("candidate_bytes", cleanup_payload)

    def test_common_path_human_output_is_not_raw_dict_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root)
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)
            self.assertIn("Bootstrap ready.", bootstrap.stdout)
            self.assertNotIn("ok:", bootstrap.stdout)

            preflight = run_cli("preflight", temp_root)
            self.assertIn("Preflight", preflight.stdout)
            self.assertNotIn("warnings:", preflight.stdout)

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
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertIn("Campaign assets built for base_2k.", build.stdout)
            self.assertNotIn("asset_root:", build.stdout)

            run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(SAMPLE_PROPOSAL),
                "--target-command-json",
                _phase6_target_command(),
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("Run completed", run.stdout)
            self.assertNotIn("status:", run.stdout)

            report = run_cli("report", temp_root, "--campaign", "base_2k")
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn("Report generated for base_2k", report.stdout)
            self.assertNotIn("artifact_paths:", report.stdout)

            doctor = run_cli("doctor", temp_root)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertIn("Doctor", doctor.stdout)
            self.assertNotIn("findings:", doctor.stdout)

            cleanup = run_cli("cleanup", temp_root, "--dry-run")
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            self.assertIn("Cleanup dry run.", cleanup.stdout)
            self.assertNotIn("candidate_count:", cleanup.stdout)


@unittest.skipIf(
    bool(missing_preflight_imports()),
    f"night integration requires preflight imports: {', '.join(missing_preflight_imports())}",
)
class NightOutputContractTests(unittest.TestCase):
    def test_night_json_envelope(self) -> None:
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
                "1",
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(night.returncode, 0, night.stderr)
            payload = json.loads(night.stdout)
            _assert_envelope(self, payload, "night")
            self.assertIn("report_path", payload)
            self.assertIn("promoted_count", payload)
            self.assertIn("failed_count", payload)


if __name__ == "__main__":
    unittest.main()
