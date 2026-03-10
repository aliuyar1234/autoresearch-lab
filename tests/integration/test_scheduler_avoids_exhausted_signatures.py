from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.dense_gpt.search_space import resolve_dense_config

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import list_campaign_experiments, upsert_campaign, upsert_experiment, upsert_proposal
from lab.memory import ingest_experiment_memory
from lab.paths import build_paths, ensure_managed_roots
from lab.proposals import normalize_proposal_payload
from lab.scheduler import generate_structured_proposal
from lab.settings import load_settings
from lab.utils import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parents[2]


def _proposal(proposal_id: str, family: str, overrides: dict[str, object], *, status: str = "completed") -> dict[str, object]:
    return normalize_proposal_payload(
        {
            "proposal_id": proposal_id,
            "campaign_id": "base_2k",
            "lane": "scout",
            "family": family,
            "kind": "structured",
            "status": status,
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


def _summary(experiment_id: str, proposal_id: str, proposal_family: str, idea_signature: str, *, status: str, disposition: str | None, validation_state: str = "not_required", metric: float | None = None) -> dict[str, object]:
    timestamp = utc_now_iso()
    return {
        "experiment_id": experiment_id,
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "scout",
        "status": status,
        "eval_split": "search_val",
        "run_purpose": "search",
        "validation_state": validation_state,
        "validation_review_id": None,
        "idea_signature": idea_signature,
        "disposition": disposition,
        "crash_class": None if status == "completed" else "assertion_failure",
        "seed": 42,
        "git_commit": "deadbeef",
        "device_profile": "test_profile",
        "backend": "test_backend",
        "proposal_family": proposal_family,
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


class SchedulerAvoidsExhaustedSignaturesTests(unittest.TestCase):
    def test_scheduler_skips_exhausted_signature_and_records_block(self) -> None:
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
            default_depth = int(resolve_dense_config(campaign, {})["model"]["depth"])

            baseline = _proposal("p_baseline", "baseline", {})
            exhausted = _proposal("p_exhausted", "exploit", {"model": {"depth": default_depth - 2}})
            exhausted_sig = str(exhausted["idea_signature"])

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, baseline, updated_at=timestamp)
                upsert_experiment(connection, _summary("exp_baseline", "p_baseline", "baseline", str(baseline["idea_signature"]), status="completed", disposition="promoted", metric=0.98), artifact_root=paths.runs_root / "exp_baseline")

                for index in (1, 2):
                    proposal_id = f"p_exhausted_{index}"
                    experiment_id = f"exp_exhausted_{index}"
                    proposal = dict(exhausted)
                    proposal["proposal_id"] = proposal_id
                    upsert_proposal(connection, proposal, updated_at=timestamp)
                    upsert_experiment(connection, _summary(experiment_id, proposal_id, "exploit", exhausted_sig, status="failed", disposition="discarded"), artifact_root=paths.runs_root / experiment_id)
                connection.commit()

                for experiment in list_campaign_experiments(connection, "base_2k"):
                    ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment)
                connection.commit()

                generated = generate_structured_proposal(connection, paths=paths, campaign=campaign, lane="scout", family="exploit")
            finally:
                connection.close()

            self.assertNotEqual(generated["idea_signature"], exhausted_sig)
            self.assertIn(exhausted_sig, generated["generation_context"]["blocked_idea_signatures"])
            self.assertTrue(generated["evidence"])


if __name__ == "__main__":
    unittest.main()
