from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.ledger.db import apply_migrations, connect, list_schema_versions
from lab.ledger.queries import append_agent_session_event, get_agent_session, list_agent_session_events, list_agent_sessions, upsert_agent_session


class AgentSessionLedgerTests(unittest.TestCase):
    def test_agent_session_migration_and_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "lab.sqlite3"
            sql_root = Path(__file__).resolve().parents[3] / "sql"

            apply_migrations(db_path, sql_root)
            self.assertIn("005_agent_sessions", list_schema_versions(db_path))

            connection = connect(db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO campaigns (
                        campaign_id, version, title, active, comparability_group, primary_metric_name,
                        manifest_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "base_2k",
                        "1.0.0",
                        "Base 2K",
                        1,
                        "base_2k",
                        "val_bpb",
                        "{}",
                        "2026-03-11T18:00:00Z",
                        "2026-03-11T18:00:00Z",
                    ),
                )
                upsert_agent_session(
                    connection,
                    {
                        "session_id": "session_base_2k_001",
                        "campaign_id": "base_2k",
                        "status": "completed",
                        "operator_mode": "agent",
                        "started_at": "2026-03-11T18:00:00Z",
                        "ended_at": "2026-03-11T18:30:00Z",
                        "hours_budget": 8.0,
                        "max_runs_budget": 12,
                        "max_structured_runs_budget": 10,
                        "max_code_runs_budget": 2,
                        "allow_confirm": True,
                        "seed_policy": "mixed",
                        "backend": "sdpa",
                        "device_profile": "test_profile",
                        "queue_refills": 2,
                        "run_count": 3,
                        "structured_run_count": 2,
                        "code_run_count": 1,
                        "confirm_run_count": 1,
                        "validation_review_count": 0,
                        "report_checkpoint_count": 1,
                        "self_review_count": 1,
                        "lane_switch_count": 1,
                        "last_lane": "confirm",
                        "stop_reason": "max_runs_budget_reached",
                        "session_manifest_path": str(root / "session_manifest.json"),
                        "retrospective_json_path": str(root / "retrospective.json"),
                        "report_json_path": str(root / "report.json"),
                        "session_summary": {"run_count": 3, "code_run_count": 1},
                        "created_at": "2026-03-11T18:00:00Z",
                        "updated_at": "2026-03-11T18:30:00Z",
                    },
                )
                append_agent_session_event(
                    connection,
                    session_id="session_base_2k_001",
                    event_type="run_completed",
                    lane="main",
                    proposal_id="p1",
                    experiment_id="exp1",
                    created_at="2026-03-11T18:05:00Z",
                    payload={"proposal_kind": "structured"},
                )
                connection.commit()

                session = get_agent_session(connection, "session_base_2k_001")
                self.assertIsNotNone(session)
                assert session is not None
                self.assertEqual(session["run_count"], 3)
                self.assertTrue(session["allow_confirm"])
                self.assertEqual(session["session_summary"]["code_run_count"], 1)

                listed = list_agent_sessions(connection, "base_2k", limit=1)
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["session_id"], "session_base_2k_001")

                events = list_agent_session_events(connection, "session_base_2k_001")
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["event_type"], "run_completed")
                self.assertEqual(events[0]["payload"]["proposal_kind"], "structured")
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
