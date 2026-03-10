from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import list_campaign_experiments, upsert_campaign, upsert_experiment, upsert_proposal
from lab.memory import ingest_experiment_memory
from lab.paths import build_paths, ensure_managed_roots
from lab.proposals import normalize_proposal_payload
from lab.scheduler import generate_structured_proposal
from lab.settings import load_settings
from lab.utils import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parents[3]


def _proposal(*, proposal_id: str, family: str, overrides: dict[str, object]) -> dict[str, object]:
    return normalize_proposal_payload(
        {
            "proposal_id": proposal_id,
            "campaign_id": "base_2k",
            "lane": "scout",
            "family": family,
            "kind": "structured",
            "status": "completed",
            "created_at": utc_now_iso(),
            "generator": "scheduler",
            "parent_ids": [],
            "hypothesis": family,
            "rationale": family,
            "config_overrides": overrides,
            "complexity_cost": 1,
            "expected_direction": "improve",
            "tags": [family],
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


def _summary(*, experiment_id: str, proposal_id: str, family: str, idea_signature: str, metric: float) -> dict[str, object]:
    timestamp = utc_now_iso()
    return {
        "experiment_id": experiment_id,
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "confirm",
        "status": "completed",
        "eval_split": "search_val",
        "run_purpose": "search",
        "validation_state": "passed",
        "validation_review_id": None,
        "idea_signature": idea_signature,
        "disposition": "promoted",
        "crash_class": None,
        "seed": 42,
        "git_commit": "deadbeef",
        "device_profile": "test_profile",
        "backend": "test_backend",
        "proposal_family": family,
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


class CombineParentSelectionTests(unittest.TestCase):
    def test_combine_proposals_cite_two_distinct_parents(self) -> None:
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

            left = _proposal(proposal_id="p_left", family="exploit", overrides={"model": {"depth": 10}})
            right = _proposal(proposal_id="p_right", family="exploit", overrides={"optimizer_groups": {"embed_lr_scale": 1.1}})

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, left, updated_at=timestamp)
                upsert_proposal(connection, right, updated_at=timestamp)
                upsert_experiment(connection, _summary(experiment_id="exp_left", proposal_id="p_left", family="exploit", idea_signature=str(left["idea_signature"]), metric=0.98), artifact_root=paths.runs_root / "exp_left")
                upsert_experiment(connection, _summary(experiment_id="exp_right", proposal_id="p_right", family="exploit", idea_signature=str(right["idea_signature"]), metric=0.979), artifact_root=paths.runs_root / "exp_right")
                connection.commit()
                for experiment in list_campaign_experiments(connection, "base_2k"):
                    ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment)
                connection.commit()

                generated = generate_structured_proposal(connection, paths=paths, campaign=campaign, lane="scout", family="combine")
            finally:
                connection.close()

            self.assertEqual(generated["family"], "combine")
            self.assertEqual(len(generated["parent_ids"]), 2)
            self.assertEqual(len(set(generated["parent_ids"])), 2)
            self.assertEqual(generated["source_experiments"], generated["parent_ids"])
            parent_evidence = [item for item in generated["evidence"] if item["role"] == "combination_parent"]
            self.assertGreaterEqual(len(parent_evidence), 2)


if __name__ == "__main__":
    unittest.main()
