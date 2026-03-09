from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import SAMPLE_PROPOSAL, SUCCESS_TARGET, run_cli, target_json_command


def _write_proposal(temp_root: Path, *, proposal_id: str, lane: str = "scout", complexity_cost: int = 1) -> Path:
    payload = json.loads(SAMPLE_PROPOSAL.read_text(encoding="utf-8"))
    payload["proposal_id"] = proposal_id
    payload["lane"] = lane
    payload["complexity_cost"] = complexity_cost
    path = temp_root / f"{proposal_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _success_command(*extra: str) -> str:
    return target_json_command(
        [
            "python",
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
            *extra,
        ]
    )


class ReplayAndScoreTests(unittest.TestCase):
    def test_score_explains_promotion_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            baseline_proposal = _write_proposal(temp_root, proposal_id="p_score_base")
            candidate_proposal = _write_proposal(temp_root, proposal_id="p_score_candidate")

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            baseline_run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(baseline_proposal),
                "--target-command-json",
                _success_command("--metric", "0.98"),
                "--json",
            )
            self.assertEqual(baseline_run.returncode, 0, baseline_run.stderr)

            candidate_run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(candidate_proposal),
                "--target-command-json",
                _success_command("--metric", "0.97"),
                "--json",
            )
            self.assertEqual(candidate_run.returncode, 0, candidate_run.stderr)
            candidate_payload = json.loads(candidate_run.stdout)

            score = run_cli("score", temp_root, "--experiment", candidate_payload["experiment_id"], "--json")
            self.assertEqual(score.returncode, 0, score.stderr)
            score_payload = json.loads(score.stdout)
            self.assertEqual(score_payload["final_disposition"], "promoted")
            self.assertEqual(score_payload["archive_effect"], "advance_to_main")
            self.assertAlmostEqual(score_payload["baseline_metric_value"], 0.98, places=6)
            self.assertAlmostEqual(score_payload["candidate_metric_value"], 0.97, places=6)
            self.assertAlmostEqual(score_payload["metric_delta"], 0.01, places=6)
            self.assertAlmostEqual(score_payload["promotion_threshold"], 0.0004, places=6)

    def test_replay_creates_new_experiment_linked_to_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            proposal_path = _write_proposal(temp_root, proposal_id="p_replay_source")

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            original_run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal_path),
                "--target-command-json",
                _success_command(),
                "--json",
            )
            self.assertEqual(original_run.returncode, 0, original_run.stderr)
            original_payload = json.loads(original_run.stdout)

            replay = run_cli(
                "replay",
                temp_root,
                "--experiment",
                original_payload["experiment_id"],
                "--target-command-json",
                _success_command("--metric", "0.969"),
                "--json",
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replay_payload = json.loads(replay.stdout)
            self.assertNotEqual(replay_payload["experiment_id"], original_payload["experiment_id"])
            self.assertEqual(replay_payload["source_experiment_id"], original_payload["experiment_id"])

            replay_root = temp_root / "artifacts" / "runs" / replay_payload["experiment_id"]
            proposal_snapshot = json.loads((replay_root / "proposal.json").read_text(encoding="utf-8"))
            manifest = json.loads((replay_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(proposal_snapshot["generator"], "replay")
            self.assertIn(original_payload["experiment_id"], proposal_snapshot["parent_ids"])
            self.assertEqual(manifest["replay_source_experiment_id"], original_payload["experiment_id"])

    def test_pre_eval_checkpoint_retained_until_scored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            proposal_path = _write_proposal(temp_root, proposal_id="p_confirm_checkpoint", lane="confirm")

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal_path),
                "--target-command-json",
                _success_command("--write-checkpoint", "--fail-after-checkpoint"),
                "--json",
            )
            self.assertEqual(run.returncode, 4, run.stderr)
            payload = json.loads(run.stdout)
            experiment_id = payload["experiment_id"]

            run_root = temp_root / "artifacts" / "runs" / experiment_id
            checkpoint_path = run_root / "checkpoints" / "pre_eval.safetensors"
            checkpoint_meta_path = run_root / "checkpoints" / "pre_eval.meta.json"
            self.assertTrue(checkpoint_path.exists())
            self.assertTrue(checkpoint_meta_path.exists())

            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            artifact_index = json.loads((run_root / "artifact_index.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["checkpoint_path"], str(checkpoint_path))
            self.assertIn("checkpoints/pre_eval.safetensors", [item["relative_path"] for item in artifact_index["artifacts"]])

            score = run_cli("score", temp_root, "--experiment", experiment_id, "--json")
            self.assertEqual(score.returncode, 0, score.stderr)
            score_payload = json.loads(score.stdout)
            self.assertEqual(score_payload["final_disposition"], "failed")
            self.assertTrue(checkpoint_path.exists())
            self.assertTrue(checkpoint_meta_path.exists())


if __name__ == "__main__":
    unittest.main()
