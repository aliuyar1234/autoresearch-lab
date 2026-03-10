from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import PHASE6_TARGET, SAMPLE_PROPOSAL, run_cli, target_json_command


def _write_proposal(temp_root: Path, *, proposal_id: str, family: str, lane: str) -> Path:
    payload = json.loads(SAMPLE_PROPOSAL.read_text(encoding="utf-8"))
    payload["proposal_id"] = proposal_id
    payload["family"] = family
    payload["lane"] = lane
    payload["parent_ids"] = []
    if family == "baseline":
        payload["config_overrides"] = {}
        payload["complexity_cost"] = 0
    path = temp_root / f"{proposal_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _phase6_command() -> str:
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


class ConfirmPromotionRequiresReviewTests(unittest.TestCase):
    def test_confirm_candidate_stays_pending_until_validation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            baseline_proposal = _write_proposal(temp_root, proposal_id="p_baseline_anchor", family="baseline", lane="scout")
            confirm_proposal = _write_proposal(temp_root, proposal_id="p_confirm_candidate", family="exploit", lane="confirm")

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            baseline_run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(baseline_proposal),
                "--target-command-json",
                _phase6_command(),
                "--json",
            )
            self.assertEqual(baseline_run.returncode, 0, baseline_run.stderr)

            candidate_run = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(confirm_proposal),
                "--target-command-json",
                _phase6_command(),
                "--json",
            )
            self.assertEqual(candidate_run.returncode, 0, candidate_run.stderr)
            candidate_payload = json.loads(candidate_run.stdout)

            inspect_before = run_cli("inspect", temp_root, "--experiment", candidate_payload["experiment_id"], "--json")
            self.assertEqual(inspect_before.returncode, 0, inspect_before.stderr)
            inspect_before_payload = json.loads(inspect_before.stdout)
            self.assertEqual(inspect_before_payload["disposition"], "pending_validation")
            self.assertEqual(inspect_before_payload["validation_state"], "pending")
            self.assertEqual(inspect_before_payload["run_purpose"], "search")
            self.assertEqual(inspect_before_payload["eval_split"], "search_val")

            score_before = run_cli("score", temp_root, "--experiment", candidate_payload["experiment_id"], "--json")
            self.assertEqual(score_before.returncode, 0, score_before.stderr)
            score_before_payload = json.loads(score_before.stdout)
            self.assertEqual(score_before_payload["final_disposition"], "pending_validation")

            validate = run_cli(
                "validate",
                temp_root,
                "--experiment",
                candidate_payload["experiment_id"],
                "--mode",
                "confirm",
                "--target-command-json",
                _phase6_command(),
                "--json",
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            validate_payload = json.loads(validate.stdout)
            self.assertEqual(validate_payload["decision"], "passed")
            self.assertGreater(validate_payload["delta_median"], 0.0)
            self.assertTrue(validate_payload["candidate_experiment_ids"])
            self.assertTrue(validate_payload["comparator_experiment_ids"])

            inspect_after = run_cli("inspect", temp_root, "--experiment", candidate_payload["experiment_id"], "--json")
            self.assertEqual(inspect_after.returncode, 0, inspect_after.stderr)
            inspect_after_payload = json.loads(inspect_after.stdout)
            self.assertEqual(inspect_after_payload["disposition"], "promoted")
            self.assertEqual(inspect_after_payload["validation_state"], "passed")
            self.assertEqual(inspect_after_payload["validation_review_id"], validate_payload["review_id"])
            self.assertEqual(inspect_after_payload["validation_review"]["decision"], "passed")

            connection = sqlite3.connect(temp_root / "lab.sqlite3")
            try:
                review_count = connection.execute("SELECT COUNT(*) FROM validation_reviews").fetchone()[0]
                promoted_count = connection.execute(
                    "SELECT COUNT(*) FROM experiments WHERE disposition = 'promoted' AND validation_state = 'passed'"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(review_count, 1)
            self.assertGreaterEqual(promoted_count, 1)


if __name__ == "__main__":
    unittest.main()
