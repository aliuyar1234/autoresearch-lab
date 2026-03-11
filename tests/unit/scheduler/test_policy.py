from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.paths import build_paths
from lab.scheduler.policy import load_reviewed_scheduler_policy, policy_summary, reviewed_scheduler_policy_path, write_scheduler_policy_suggestion
from lab.settings import load_settings

REPO_ROOT = Path(__file__).resolve().parents[3]


class SchedulerPolicyTests(unittest.TestCase):
    def test_reviewed_policy_round_trip(self) -> None:
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
            suggestion_path = write_scheduler_policy_suggestion(
                paths=paths,
                campaign_id="base_2k",
                family_weights={"exploit": 1.8, "combine": 0.5},
                preferred_families=["exploit"],
                blocked_families=["novel"],
                rationale="Prefer compounding on validated anchors before opening novelty.",
                notes=["generated in test"],
                review_state="draft",
            )
            self.assertTrue(suggestion_path.exists())

            active_path = reviewed_scheduler_policy_path(paths, "base_2k")
            active_path.parent.mkdir(parents=True, exist_ok=True)
            active_path.write_text(
                suggestion_path.read_text(encoding="utf-8").replace('"review_state": "draft"', '"review_state": "reviewed"'),
                encoding="utf-8",
            )

            policy = load_reviewed_scheduler_policy(paths, "base_2k")
            self.assertIsNotNone(policy)
            assert policy is not None
            summary = policy_summary(policy)
            self.assertEqual(summary["preferred_families"], ["exploit"])
            self.assertEqual(summary["blocked_families"], ["novel"])
            self.assertAlmostEqual(summary["family_weights"]["exploit"], 1.8)


if __name__ == "__main__":
    unittest.main()
