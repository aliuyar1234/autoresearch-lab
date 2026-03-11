from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.paths import build_paths, ensure_managed_roots
from lab.scheduler import plan_structured_queue
from lab.settings import load_settings


REPO_ROOT = Path(__file__).resolve().parents[3]


class QueuePersistenceTests(unittest.TestCase):
    def test_plan_structured_queue_persists_retrieval_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                cache_root=temp_root / "cache",
                env={},
            )
            paths = build_paths(settings)
            ensure_managed_roots(paths)
            apply_migrations(paths.db_path, paths.sql_root)
            campaign = load_campaign(paths, "base_2k")

            connection = connect(paths.db_path)
            try:
                planned = plan_structured_queue(
                    connection,
                    paths=paths,
                    campaign=campaign,
                    count=3,
                    lane_mix=(("scout", 1),),
                    persist=True,
                )
                rows = connection.execute(
                    "SELECT retrieval_event_id FROM retrieval_events ORDER BY retrieval_event_id"
                ).fetchall()
            finally:
                connection.close()

            persisted_ids = [str(row["retrieval_event_id"]) for row in rows]
            planned_ids = [str(item["retrieval_event_id"]) for item in planned]
            self.assertEqual(sorted(persisted_ids), sorted(planned_ids))
            self.assertEqual(len(persisted_ids), len(planned))


if __name__ == "__main__":
    unittest.main()
