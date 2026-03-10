from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import connect
from lab.ledger.queries import list_memory_records, upsert_campaign
from lab.paths import build_paths
from lab.settings import load_settings
from lab.utils import utc_now_iso

from ._cli_helpers import CODE_PATCH_TARGET, REPO_ROOT, run_cli, target_json_command
from ._code_proposal_helpers import build_train_patch, sample_code_patch_proposal, seed_code_proposal_state


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


class CodeProposalImportLineageTests(unittest.TestCase):
    def test_import_and_run_preserve_code_lane_lineage(self) -> None:
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
            proposal = sample_code_patch_proposal(proposal_id="p_code_patch_import_lineage", lane="main")

            connection = connect(paths.db_path)
            try:
                upsert_campaign(connection, campaign, timestamp=utc_now_iso())
                seed_code_proposal_state(connection, campaign=campaign, proposal=proposal, paths=paths)
                connection.commit()
            finally:
                connection.close()

            export = run_cli("export-code-proposal", temp_root, "--proposal-id", str(proposal["proposal_id"]), "--json")
            self.assertEqual(export.returncode, 0, export.stderr)

            patch_path = temp_root / "returned.patch"
            patch_path.write_text(build_train_patch(), encoding="utf-8")

            imported = run_cli(
                "import-code-proposal",
                temp_root,
                "--proposal-id",
                str(proposal["proposal_id"]),
                "--patch-path",
                str(patch_path),
                "--json",
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            imported_payload = json.loads(imported.stdout)
            self.assertEqual(imported_payload["return_kind"], "patch")
            self.assertEqual(imported_payload["diff_stats"]["files_changed"], 1)
            self.assertGreater(imported_payload["diff_stats"]["lines_added"], 0)

            inspect = run_cli("inspect", temp_root, "--proposal", str(proposal["proposal_id"]), "--json")
            self.assertEqual(inspect.returncode, 0, inspect.stderr)
            inspect_payload = json.loads(inspect.stdout)
            self.assertTrue(inspect_payload["code_patch_imported"])
            self.assertEqual(inspect_payload["code_patch_diff_stats"]["files_changed"], 1)
            self.assertEqual(len(inspect_payload["code_patch_evidence_memory_ids"]), 2)

            run = run_cli(
                "run",
                temp_root,
                "--proposal-id",
                str(proposal["proposal_id"]),
                "--target-command-json",
                _code_patch_target_command(),
                "--json",
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            run_payload = json.loads(run.stdout)
            self.assertEqual(run_payload["status"], "completed")

            artifact_root = Path(run_payload["artifact_root"])
            code_import_root = artifact_root / "code_import"
            self.assertTrue((code_import_root / "return_manifest.json").exists())
            self.assertTrue((code_import_root / "returned.patch").exists())
            self.assertTrue((code_import_root / "evidence.json").exists())
            self.assertTrue((code_import_root / "validation_targets.json").exists())
            self.assertTrue((code_import_root / "proposal_context.md").exists())

            return_manifest = json.loads((code_import_root / "return_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(return_manifest["proposal_id"], proposal["proposal_id"])
            self.assertEqual(return_manifest["changed_files"], ["train.py"])
            self.assertEqual(return_manifest["diff_stats"]["files_changed"], 1)
            self.assertEqual(len(return_manifest["evidence_memory_ids"]), 2)
            self.assertTrue(str(return_manifest["pack_root"]).endswith("code_pack"))
            self.assertIsNotNone(return_manifest["validation_targets_path"])
            self.assertIsNotNone(return_manifest["evidence_path"])

            evidence_payload = json.loads((code_import_root / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence_payload["citation_count"], 2)

            validation_targets = json.loads((code_import_root / "validation_targets.json").read_text(encoding="utf-8"))
            self.assertEqual(validation_targets["primary_metric"]["name"], "val_bpb")

            connection = connect(paths.db_path)
            try:
                memory_records = list_memory_records(connection, campaign_id="base_2k")
            finally:
                connection.close()
            experiment_records = [
                item
                for item in memory_records
                if item["source_ref"] == run_payload["experiment_id"] and item["record_type"] == "experiment_result"
            ]
            self.assertTrue(experiment_records)
            code_patch_lineage = experiment_records[0]["payload"]["code_patch"]
            self.assertEqual(code_patch_lineage["diff_stats"]["files_changed"], 1)
            self.assertEqual(code_patch_lineage["target_files"], ["train.py"])
            self.assertEqual(len(code_patch_lineage["evidence_memory_ids"]), 2)
            self.assertEqual(code_patch_lineage["validation_targets"]["primary_metric"]["name"], "val_bpb")


if __name__ == "__main__":
    unittest.main()
