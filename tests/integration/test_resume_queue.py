from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import list_campaign_experiments, upsert_campaign, upsert_proposal
from lab.runner.materialize import materialize_run
from lab.settings import load_settings
from lab.paths import build_paths
from lab.utils import utc_now_iso

from ._cli_helpers import PHASE6_TARGET, REPO_ROOT, run_cli, target_json_command


def _phase6_target_command() -> str:
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


def _write_base_source_docs(source_root: Path) -> None:
    source_root.mkdir(parents=True, exist_ok=True)
    docs = {
        "shard_00001.parquet": "train example one",
        "shard_00002.parquet": "train example two",
        "shard_06540.parquet": "locked validation",
        "shard_06541.parquet": "audit validation",
        "shard_06542.parquet": "search validation",
    }
    for name, text in docs.items():
        (source_root / name).write_text(text, encoding="utf-8")


def _write_proposal(
    root: Path,
    *,
    campaign_id: str,
    proposal_id: str,
    family: str,
    lane: str,
    status: str = "queued",
) -> Path:
    proposal_path = root / f"{proposal_id}.json"
    payload = _proposal_payload(
        campaign_id=campaign_id,
        proposal_id=proposal_id,
        family=family,
        lane=lane,
        status=status,
    )
    proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return proposal_path


def _proposal_payload(*, campaign_id: str, proposal_id: str, family: str, lane: str, status: str) -> dict[str, object]:
    return {
        "proposal_id": proposal_id,
        "campaign_id": campaign_id,
        "lane": lane,
        "family": family,
        "kind": "structured",
        "status": status,
        "created_at": "2026-03-09T18:00:00Z",
        "generator": "test",
        "parent_ids": [],
        "hypothesis": f"Resume fixture for {family}",
        "rationale": "Exercise queue reconstruction after interruption.",
        "config_overrides": {},
        "complexity_cost": 0,
        "expected_direction": "improve",
        "tags": [family],
        "novelty_reason": None,
        "notes": None,
        "guardrails": {"max_peak_vram_gb": 92},
    }


class ResumeQueueTests(unittest.TestCase):
    def test_resume_reconstructs_interrupted_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            source_root = temp_root / "raw"
            _write_base_source_docs(source_root)
            build = run_cli(
                "campaign",
                temp_root,
                "build",
                "--campaign",
                "base_2k",
                "--source-dir",
                str(source_root),
                "--json",
            )
            self.assertEqual(build.returncode, 0, build.stderr)

            proposal_dir = temp_root / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)

            baseline = _write_proposal(
                proposal_dir,
                campaign_id="base_2k",
                proposal_id="p_resume_baseline",
                family="baseline",
                lane="scout",
            )
            baseline_result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(baseline),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(baseline_result.returncode, 0, baseline_result.stderr)

            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            campaign = load_campaign(paths, "base_2k")
            interrupted_proposal = _proposal_payload(
                campaign_id="base_2k",
                proposal_id="p_resume_interrupted",
                family="exploit",
                lane="main",
                status="running",
            )

            apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, interrupted_proposal, updated_at=timestamp)
                materialized = materialize_run(
                    paths=paths,
                    proposal=interrupted_proposal,
                    campaign=campaign,
                    run_command=[sys.executable, str(PHASE6_TARGET)],
                    seed=42,
                    time_budget_seconds=1,
                    device_profile="test_profile",
                    backend="test_backend",
                )
                materialized.stderr_path.write_text("KeyboardInterrupt: simulated interruption\n", encoding="utf-8")
                connection.commit()
            finally:
                connection.close()

            night = run_cli(
                "night",
                temp_root,
                "--campaign",
                "base_2k",
                "--hours",
                "0",
                "--max-runs",
                "1",
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(night.returncode, 0, night.stderr)
            night_payload = json.loads(night.stdout)
            self.assertTrue(night_payload["ok"])
            self.assertEqual(night_payload["run_count"], 1)
            self.assertEqual(len(night_payload["resume"]["synthesized_experiments"]), 1)
            self.assertEqual(len(night_payload["resume"]["requeued_proposals"]), 1)

            report_json = Path(night_payload["report"]["artifact_paths"]["report_json"])
            report_payload = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertTrue(report_payload["session_notes"])

            connection = connect(paths.db_path)
            try:
                experiments = list_campaign_experiments(connection, "base_2k")
            finally:
                connection.close()
            interrupted_rows = [row for row in experiments if str(row.get("crash_class")) == "interrupted"]
            resumed_rows = [
                row
                for row in experiments
                if str(row.get("proposal_id")) == "p_resume_interrupted" and str(row.get("status")) == "completed"
            ]
            self.assertTrue(interrupted_rows)
            self.assertTrue(resumed_rows)
            self.assertGreaterEqual(len(experiments), 3)


if __name__ == "__main__":
    unittest.main()
