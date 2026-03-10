from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import upsert_campaign, upsert_experiment, upsert_proposal
from lab.paths import build_paths, ensure_managed_roots
from lab.scheduler import choose_family, generate_structured_proposal, novelty_tags, plan_structured_queue
from lab.settings import load_settings
from lab.utils import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parents[2]


def _proposal(*, proposal_id: str, family: str, overrides: dict[str, object], complexity_cost: int = 0) -> dict[str, object]:
    return {
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "scout",
        "family": family,
        "kind": "structured",
        "status": "completed",
        "created_at": utc_now_iso(),
        "generator": "scheduler",
        "parent_ids": [],
        "hypothesis": "test hypothesis",
        "rationale": "test rationale",
        "config_overrides": overrides,
        "complexity_cost": complexity_cost,
        "expected_direction": "improve",
        "tags": [family],
        "novelty_reason": None,
        "notes": None,
        "guardrails": {"max_peak_vram_gb": 92},
    }


def _summary(*, experiment_id: str, proposal_id: str, metric: float, complexity_cost: int = 0) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "scout",
        "status": "completed",
        "disposition": "promoted",
        "crash_class": None,
        "proposal_family": "baseline",
        "proposal_kind": "structured",
        "complexity_cost": complexity_cost,
        "primary_metric_name": "val_bpb",
        "primary_metric_value": metric,
        "metric_delta": None,
        "budget_seconds": 90,
        "train_seconds": 1.0,
        "eval_seconds": 0.1,
        "compile_seconds": 0.0,
        "tokens_processed": 2048,
        "tokens_per_second": 4096.0,
        "steady_state_mfu": 0.4,
        "peak_vram_gb": 1.0,
        "param_count": 1,
        "backend": "test_backend",
        "device_profile": "test_profile",
        "seed": 42,
        "config_fingerprint": "abc123deadbeef",
        "git_commit": "deadbeef",
        "warnings": [],
        "checkpoint_path": None,
        "summary_version": "1.0.0",
        "started_at": utc_now_iso(),
        "ended_at": utc_now_iso(),
    }


class SchedulerPolicyTests(unittest.TestCase):
    def test_scheduler_respects_lane_mix(self) -> None:
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

            connection = connect(paths.db_path)
            try:
                upsert_campaign(connection, campaign, timestamp=utc_now_iso())
                queue = plan_structured_queue(connection, paths=paths, campaign=campaign, count=6)
            finally:
                connection.close()

            counts = Counter(item["lane"] for item in queue)
            self.assertEqual(counts["scout"], 3)
            self.assertEqual(counts["main"], 2)
            self.assertEqual(counts["confirm"], 1)

    def test_scheduler_prefers_ablation_after_complex_win(self) -> None:
        family = choose_family(
            has_baseline=True,
            recent_history=[
                {
                    "proposal_family": "exploit",
                    "crash_class": None,
                    "disposition": "promoted",
                }
            ],
            have_orthogonal_winners_to_combine=False,
            should_ablate_recent_complex_win=True,
            novelty_gap=False,
        )
        self.assertEqual(family, "ablation")

    def test_generate_structured_baseline_when_absent(self) -> None:
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

            connection = connect(paths.db_path)
            try:
                upsert_campaign(connection, campaign, timestamp=utc_now_iso())
                generated = generate_structured_proposal(connection, paths=paths, campaign=campaign, lane="scout")
                connection.commit()
            finally:
                connection.close()

            self.assertEqual(generated["family"], "baseline")
            self.assertEqual(generated["kind"], "structured")
            self.assertEqual(generated["config_overrides"], {})
            self.assertEqual(generated["parent_ids"], [])
            proposal_path = paths.proposals_root / f"{generated['proposal_id']}.json"
            self.assertTrue(proposal_path.exists())

    def test_generate_structured_exploit_avoids_duplicate_fingerprint(self) -> None:
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

            baseline = _proposal(proposal_id="p_base_2k_baseline_scout_0001", family="baseline", overrides={})
            duplicate = _proposal(
                proposal_id="p_base_2k_exploit_scout_0002",
                family="exploit",
                overrides={"optimizer_groups": {"embed_lr_scale": 1.1}},
                complexity_cost=1,
            )

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, baseline, updated_at=timestamp)
                upsert_experiment(
                    connection,
                    _summary(experiment_id="exp_baseline_0001", proposal_id=baseline["proposal_id"], metric=0.98),
                    artifact_root=paths.runs_root / "exp_baseline_0001",
                )
                upsert_proposal(connection, duplicate, updated_at=timestamp)
                connection.commit()

                generated = generate_structured_proposal(connection, paths=paths, campaign=campaign, lane="scout")
            finally:
                connection.close()

            self.assertEqual(generated["family"], "exploit")
            self.assertIn("exp_baseline_0001", generated["parent_ids"])
            self.assertNotEqual(
                generated["config_overrides"],
                {"optimizer_groups": {"embed_lr_scale": 1.1}},
            )

    def test_novelty_tagging(self) -> None:
        tags = novelty_tags({"optimizer_groups": {"embed_lr_scale": 1.25}, "model": {"window_pattern": "LLLL"}})
        self.assertIn("optimizer_groups.embed_lr_scale", tags)
        self.assertIn("model.window_pattern:LLLL", tags)


if __name__ == "__main__":
    unittest.main()
