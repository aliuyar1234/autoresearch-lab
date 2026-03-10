from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from lab.cleanup import select_cleanup_candidates

from tests.integration._cli_helpers import PHASE6_TARGET, run_cli, target_json_command


def _write_proposal(root: Path, *, proposal_id: str) -> Path:
    proposal_path = root / f"{proposal_id}.json"
    payload = {
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "scout",
        "family": "baseline",
        "kind": "structured",
        "status": "queued",
        "created_at": "2026-03-09T18:00:00Z",
        "generator": "test",
        "parent_ids": [],
        "hypothesis": "Exercise cleanup and doctor coverage.",
        "rationale": "Keep Phase 7 diagnostics honest.",
        "config_overrides": {},
        "complexity_cost": 0,
        "expected_direction": "improve",
        "tags": ["baseline"],
        "novelty_reason": None,
        "notes": None,
        "guardrails": {"max_peak_vram_gb": 92},
    }
    proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return proposal_path


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


class CleanupPolicyTests(unittest.TestCase):
    def test_cleanup_never_deletes_retained_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            run_root = artifacts_root / "runs" / "exp_demo"
            run_root.mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "id": 1,
                    "experiment_id": "exp_demo",
                    "artifact_root": str(run_root),
                    "relative_path": "stdout.log",
                    "kind": "stdout",
                    "retention_class": "discardable",
                    "size_bytes": 12,
                },
                {
                    "id": 2,
                    "experiment_id": "exp_demo",
                    "artifact_root": str(run_root),
                    "relative_path": "summary.json",
                    "kind": "summary",
                    "retention_class": "full",
                    "size_bytes": 128,
                },
                {
                    "id": 3,
                    "experiment_id": "exp_demo",
                    "artifact_root": str(run_root),
                    "relative_path": "checkpoints/pre_eval.safetensors",
                    "kind": "checkpoint",
                    "retention_class": "promoted",
                    "size_bytes": 2048,
                },
                {
                    "id": 4,
                    "experiment_id": "exp_demo",
                    "artifact_root": str(run_root),
                    "relative_path": "stderr.log",
                    "kind": "stderr",
                    "retention_class": "crash_exemplar",
                    "size_bytes": 64,
                },
            ]

            candidates, skipped = select_cleanup_candidates(rows, artifacts_root=artifacts_root)

            self.assertEqual([item["retention_class"] for item in candidates], ["discardable"])
            self.assertEqual(len(skipped), 3)
            self.assertTrue(all(item["reason"] == "retained" for item in skipped))

    def test_doctor_detects_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            proposal_dir = temp_root / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            proposal_path = _write_proposal(proposal_dir, proposal_id="p_doctor_missing_artifact")
            result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal_path),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            summary_path = Path(payload["summary_path"])
            summary_path.unlink()

            doctor = run_cli("doctor", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(doctor.returncode, 3, doctor.stdout)
            doctor_payload = json.loads(doctor.stdout)
            finding_types = [item["type"] for item in doctor_payload["findings"]]
            self.assertIn("missing_artifact", finding_types)

    def test_doctor_is_idempotent_and_classifies_artifact_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            proposal_dir = temp_root / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            proposal_path = _write_proposal(proposal_dir, proposal_id="p_doctor_repeat")
            result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal_path),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            Path(payload["summary_path"]).unlink()

            first = run_cli("doctor", temp_root, "--campaign", "base_2k", "--json")
            second = run_cli("doctor", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(first.returncode, 3, first.stdout)
            self.assertEqual(second.returncode, 3, second.stdout)

            first_payload = json.loads(first.stdout)
            second_payload = json.loads(second.stdout)
            self.assertEqual(first_payload["counts"], second_payload["counts"])
            self.assertEqual(
                [(item["type"], item["problem_class"]) for item in first_payload["findings"]],
                [(item["type"], item["problem_class"]) for item in second_payload["findings"]],
            )
            self.assertGreater(first_payload["problem_counts"]["artifact"], 0)

    def test_cleanup_dry_run_and_apply_share_selection_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            proposal_dir = temp_root / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            proposal_path = _write_proposal(proposal_dir, proposal_id="p_cleanup_apply")
            result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal_path),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            dry_run = run_cli("cleanup", temp_root, "--dry-run", "--json")
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            dry_payload = json.loads(dry_run.stdout)
            self.assertGreater(dry_payload["candidate_count"], 0)
            self.assertGreaterEqual(dry_payload["candidate_bytes"], 0)
            self.assertEqual(dry_payload["status"], "dry_run")

            apply = run_cli("cleanup", temp_root, "--apply", "--json")
            self.assertEqual(apply.returncode, 0, apply.stderr)
            apply_payload = json.loads(apply.stdout)
            self.assertEqual(apply_payload["candidate_count"], dry_payload["candidate_count"])
            self.assertEqual(apply_payload["candidate_bytes"], dry_payload["candidate_bytes"])
            self.assertEqual(apply_payload["deleted_count"], dry_payload["candidate_count"])
            self.assertEqual(apply_payload["status"], "applied")

            after = run_cli("cleanup", temp_root, "--dry-run", "--json")
            self.assertEqual(after.returncode, 0, after.stderr)
            after_payload = json.loads(after.stdout)
            self.assertEqual(after_payload["candidate_count"], 0)
            self.assertEqual(after_payload["status"], "clean")


if __name__ == "__main__":
    unittest.main()
