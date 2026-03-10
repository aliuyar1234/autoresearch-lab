from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import upsert_campaign, upsert_experiment, upsert_proposal
from lab.paths import build_paths, ensure_managed_roots
from lab.proposals import normalize_proposal_payload
from lab.scheduler import generate_structured_proposal
from lab.settings import load_settings
from lab.utils import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parents[3]


def _proposal_payload(proposal_id: str, overrides: dict[str, object]) -> dict[str, object]:
    return normalize_proposal_payload(
        {
            "proposal_id": proposal_id,
            "campaign_id": "base_2k",
            "lane": "scout",
            "family": "exploit",
            "kind": "structured",
            "status": "completed",
            "created_at": utc_now_iso(),
            "generator": "scheduler",
            "parent_ids": [],
            "hypothesis": "test",
            "rationale": "test",
            "config_overrides": overrides,
            "complexity_cost": 1,
            "expected_direction": "improve",
            "tags": ["exploit"],
            "evidence": [],
            "generation_context": {
                "family_selector_reason": "test",
                "anchor_experiment_ids": [],
                "blocked_idea_signatures": [],
                "retrieval_event_id": None,
                "selection_rank": 1,
                "selection_score": None,
            },
        }
    )


def _experiment_summary(experiment_id: str, proposal_id: str, idea_signature: str, metric: float, disposition: str, validation_state: str) -> dict[str, object]:
    timestamp = utc_now_iso()
    return {
        "experiment_id": experiment_id,
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "confirm" if validation_state == "passed" else "main",
        "status": "completed",
        "eval_split": "search_val",
        "run_purpose": "search",
        "validation_state": validation_state,
        "validation_review_id": None,
        "idea_signature": idea_signature,
        "disposition": disposition,
        "crash_class": None,
        "seed": 42,
        "git_commit": "deadbeef",
        "device_profile": "test_profile",
        "backend": "test_backend",
        "proposal_family": "exploit",
        "proposal_kind": "structured",
        "complexity_cost": 1,
        "budget_seconds": 90,
        "primary_metric_name": "val_bpb",
        "primary_metric_value": metric,
        "metric_delta": None,
        "tokens_per_second": 1000.0,
        "peak_vram_gb": 1.0,
        "started_at": timestamp,
        "ended_at": timestamp,
    }


class ValidatedAnchorPreferenceTests(unittest.TestCase):
    def test_exploit_prefers_validated_anchor_over_raw_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            ensure_managed_roots(paths)
            apply_migrations(paths.db_path, paths.sql_root)
            campaign = load_campaign(paths, "base_2k")
            validated = _proposal_payload("p_validated", {"model": {"depth": 10}})
            raw = _proposal_payload("p_raw", {"model": {"depth": 12}})

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, validated, updated_at=timestamp)
                upsert_proposal(connection, raw, updated_at=timestamp)
                upsert_experiment(connection, _experiment_summary("exp_validated", "p_validated", str(validated["idea_signature"]), 0.99, "promoted", "passed"), artifact_root=paths.runs_root / "exp_validated")
                upsert_experiment(connection, _experiment_summary("exp_raw", "p_raw", str(raw["idea_signature"]), 0.95, "completed", "not_required"), artifact_root=paths.runs_root / "exp_raw")
                connection.commit()

                generated = generate_structured_proposal(connection, paths=paths, campaign=campaign, lane="scout", family="exploit")
            finally:
                connection.close()

            self.assertEqual(generated["parent_ids"], ["exp_validated"])


if __name__ == "__main__":
    unittest.main()
