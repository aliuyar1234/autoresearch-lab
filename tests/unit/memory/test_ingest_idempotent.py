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
from lab.settings import load_settings
from lab.utils import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parents[3]


class MemoryIngestIdempotentTests(unittest.TestCase):
    def test_experiment_memory_backfill_is_idempotent(self) -> None:
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
            proposal = normalize_proposal_payload(
                {
                    "proposal_id": "p_ingest_0001",
                    "campaign_id": "base_2k",
                    "lane": "scout",
                    "family": "baseline",
                    "kind": "structured",
                    "status": "completed",
                    "created_at": utc_now_iso(),
                    "generator": "scheduler",
                    "parent_ids": [],
                    "hypothesis": "baseline",
                    "rationale": "baseline",
                    "config_overrides": {},
                    "complexity_cost": 0,
                    "expected_direction": "improve",
                    "tags": ["baseline"],
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

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, proposal, updated_at=timestamp)
                upsert_experiment(
                    connection,
                    {
                        "experiment_id": "exp_ingest_0001",
                        "proposal_id": proposal["proposal_id"],
                        "campaign_id": "base_2k",
                        "lane": "scout",
                        "status": "completed",
                        "eval_split": "search_val",
                        "run_purpose": "baseline",
                        "validation_state": "not_required",
                        "validation_review_id": None,
                        "idea_signature": proposal["idea_signature"],
                        "disposition": "promoted",
                        "crash_class": None,
                        "seed": 42,
                        "git_commit": "deadbeef",
                        "device_profile": "test_profile",
                        "backend": "test_backend",
                        "proposal_family": "baseline",
                        "proposal_kind": "structured",
                        "complexity_cost": 0,
                        "budget_seconds": 90,
                        "primary_metric_name": "val_bpb",
                        "primary_metric_value": 0.97,
                        "metric_delta": None,
                        "tokens_per_second": 1000.0,
                        "peak_vram_gb": 1.0,
                        "started_at": timestamp,
                        "ended_at": timestamp,
                    },
                    artifact_root=paths.runs_root / "exp_ingest_0001",
                )
                connection.commit()
                experiment = list_campaign_experiments(connection, "base_2k")[0]
                created_first, skipped_first = ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment)
                created_second, skipped_second = ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment)
                count = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(created_first, 2)
            self.assertEqual(skipped_first, 0)
            self.assertEqual(created_second, 0)
            self.assertEqual(skipped_second, 2)
            self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
