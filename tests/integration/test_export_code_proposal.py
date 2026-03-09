from __future__ import annotations

import difflib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import connect
from lab.ledger.queries import upsert_campaign, upsert_experiment, upsert_proposal
from lab.paths import build_paths
from lab.settings import load_settings
from lab.utils import utc_now_iso

from ._cli_helpers import CODE_PATCH_TARGET, REPO_ROOT, SUCCESS_TARGET, run_cli, target_json_command


def _target_command() -> str:
    return target_json_command(
        [
            sys.executable,
            str(SUCCESS_TARGET),
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


def _code_patch_target_command() -> str:
    return target_json_command(
        [
            sys.executable,
            str(CODE_PATCH_TARGET),
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


def _summary(*, experiment_id: str, proposal_id: str, metric: float, disposition: str = "promoted") -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "proposal_id": proposal_id,
        "campaign_id": "base_2k",
        "lane": "main",
        "status": "completed",
        "disposition": disposition,
        "crash_class": None,
        "proposal_family": "manual",
        "proposal_kind": "code_patch",
        "complexity_cost": 4,
        "primary_metric_name": "val_bpb",
        "primary_metric_value": metric,
        "metric_delta": None,
        "budget_seconds": 300,
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


class ExportCodeProposalTests(unittest.TestCase):
    def test_queue_fill_from_archive_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            for _ in range(2):
                run = run_cli(
                    "run",
                    temp_root,
                    "--campaign",
                    "base_2k",
                    "--generate",
                    "structured",
                    "--lane",
                    "scout",
                    "--target-command-json",
                    _target_command(),
                    "--json",
                )
                self.assertEqual(run.returncode, 0, run.stderr)

            queue = run_cli("campaign", temp_root, "queue", "--campaign", "base_2k", "--count", "4", "--apply", "--json")
            self.assertEqual(queue.returncode, 0, queue.stderr)
            payload = json.loads(queue.stdout)
            self.assertEqual(payload["count"], 4)
            self.assertTrue(payload["apply"])

            inspect = run_cli("inspect", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertGreaterEqual(inspect_payload["queued_proposal_count"], 4)
            self.assertEqual(len(set(item["proposal_id"] for item in payload["proposals"])), 4)

    def test_inspect_campaign_shows_archive_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            for _ in range(2):
                run = run_cli(
                    "run",
                    temp_root,
                    "--campaign",
                    "base_2k",
                    "--generate",
                    "structured",
                    "--lane",
                    "scout",
                    "--target-command-json",
                    _target_command(),
                    "--json",
                )
                self.assertEqual(run.returncode, 0, run.stderr)

            inspect = run_cli("inspect", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            payload = json.loads(inspect.stdout)
            self.assertEqual(payload["kind"], "campaign")
            self.assertEqual(payload["campaign_id"], "base_2k")
            self.assertTrue(payload["archive_row_count"] > 0)
            self.assertTrue((temp_root / "artifacts" / "archive" / "base_2k" / "archive_snapshot.json").exists())
            self.assertIn("pareto", payload["archive_buckets"])

    def test_export_code_proposal_writes_self_contained_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            campaign = load_campaign(paths, "base_2k")
            proposal = {
                "proposal_id": "p_code_patch_0001",
                "campaign_id": "base_2k",
                "lane": "main",
                "family": "manual",
                "kind": "code_patch",
                "status": "queued",
                "created_at": utc_now_iso(),
                "generator": "human",
                "parent_ids": ["exp_parent_0001"],
                "hypothesis": "A small trainer patch may improve the main lane without changing campaign semantics.",
                "rationale": "The code lane should be able to work from a self-contained exported pack.",
                "config_overrides": {},
                "complexity_cost": 4,
                "expected_direction": "improve",
                "tags": ["manual", "code_patch"],
                "novelty_reason": None,
                "notes": None,
                "guardrails": {"max_peak_vram_gb": 92},
                "code_patch": {
                    "target_files": ["train.py", "lab/cli.py"],
                    "base_commit": "deadbeef",
                    "patch_path": None,
                    "acceptance_summary": "Keep the change constrained and preserve structured runner outputs.",
                    "worktree_id": None,
                },
            }

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, proposal, updated_at=timestamp)
                upsert_experiment(
                    connection,
                    _summary(experiment_id="exp_parent_0001", proposal_id=proposal["proposal_id"], metric=0.971),
                    artifact_root=paths.runs_root / "exp_parent_0001",
                )
                upsert_experiment(
                    connection,
                    _summary(experiment_id="exp_best_0001", proposal_id=proposal["proposal_id"], metric=0.969),
                    artifact_root=paths.runs_root / "exp_best_0001",
                )
                connection.commit()
            finally:
                connection.close()

            export = run_cli("export-code-proposal", temp_root, "--proposal-id", proposal["proposal_id"], "--json")
            self.assertEqual(export.returncode, 0, export.stderr)
            payload = json.loads(export.stdout)
            pack_root = Path(payload["pack_root"])
            self.assertTrue((pack_root / "proposal.json").exists())
            self.assertTrue((pack_root / "README.md").exists())
            self.assertTrue((pack_root / "acceptance_criteria.md").exists())
            self.assertTrue((pack_root / "target_files.txt").exists())
            self.assertTrue((pack_root / "return_instructions.md").exists())
            self.assertTrue((pack_root / "context" / "campaign.json").exists())
            self.assertTrue((pack_root / "context" / "best_comparator.json").exists())
            self.assertTrue((pack_root / "context" / "parent_runs.json").exists())
            self.assertTrue((pack_root / "context" / "files" / "train.py").exists())
            self.assertTrue((pack_root / "context" / "files" / "lab" / "cli.py").exists())

            exported_proposal = json.loads((pack_root / "proposal.json").read_text(encoding="utf-8"))
            self.assertEqual(exported_proposal["kind"], "code_patch")
            self.assertEqual(exported_proposal["code_patch"]["target_files"], ["train.py", "lab/cli.py"])

    def test_import_code_proposal_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            campaign = load_campaign(paths, "base_2k")
            proposal = {
                "proposal_id": "p_code_patch_roundtrip",
                "campaign_id": "base_2k",
                "lane": "main",
                "family": "manual",
                "kind": "code_patch",
                "status": "queued",
                "created_at": utc_now_iso(),
                "generator": "human",
                "parent_ids": [],
                "hypothesis": "Returned code patch should execute from an isolated snapshot.",
                "rationale": "Sign off the code lane round-trip path.",
                "config_overrides": {},
                "complexity_cost": 4,
                "expected_direction": "improve",
                "tags": ["manual", "code_patch"],
                "novelty_reason": None,
                "notes": None,
                "guardrails": {"max_peak_vram_gb": 92},
                "code_patch": {
                    "target_files": ["train.py"],
                    "base_commit": "deadbeef",
                    "patch_path": None,
                    "acceptance_summary": "Imported code proposal should run through the normal runner path.",
                    "worktree_id": None,
                },
            }

            connection = connect(paths.db_path)
            try:
                timestamp = utc_now_iso()
                upsert_campaign(connection, campaign, timestamp=timestamp)
                upsert_proposal(connection, proposal, updated_at=timestamp)
                connection.commit()
            finally:
                connection.close()

            export = run_cli("export-code-proposal", temp_root, "--proposal-id", proposal["proposal_id"], "--json")
            self.assertEqual(export.returncode, 0, export.stderr)

            patch_path = temp_root / "returned.patch"
            original = (REPO_ROOT / "train.py").read_text(encoding="utf-8").splitlines(keepends=True)
            modified = original + ["# code-patch roundtrip marker\n"]
            patch_text = "".join(
                difflib.unified_diff(
                    original,
                    modified,
                    fromfile="a/train.py",
                    tofile="b/train.py",
                    n=3,
                )
            )
            patch_path.write_text(patch_text, encoding="utf-8")

            imported = run_cli(
                "import-code-proposal",
                temp_root,
                "--proposal-id",
                proposal["proposal_id"],
                "--patch-path",
                str(patch_path),
                "--json",
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            imported_payload = json.loads(imported.stdout)
            self.assertEqual(imported_payload["return_kind"], "patch")
            self.assertTrue(Path(imported_payload["patch_path"]).exists())

            inspect = run_cli("inspect", temp_root, "--proposal", proposal["proposal_id"], "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertTrue(inspect_payload["code_patch_imported"])

            run = run_cli(
                "run",
                temp_root,
                "--proposal-id",
                proposal["proposal_id"],
                "--target-command-json",
                _code_patch_target_command(),
                "--json",
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertEqual(run_payload["status"], "completed")
            self.assertEqual(run_payload["proposal_kind"], "code_patch")


if __name__ == "__main__":
    unittest.main()
