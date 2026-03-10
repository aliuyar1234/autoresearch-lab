from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.ledger.db import connect
from lab.ledger.queries import upsert_campaign
from lab.paths import build_paths
from lab.settings import load_settings
from lab.utils import utc_now_iso

from ._cli_helpers import REPO_ROOT, run_cli
from ._code_proposal_helpers import sample_code_patch_proposal, seed_code_proposal_state


class CodeProposalExportEvidenceTests(unittest.TestCase):
    def test_export_pack_includes_evidence_and_validation_context(self) -> None:
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
            proposal = sample_code_patch_proposal(proposal_id="p_code_patch_export_evidence", lane="confirm")

            connection = connect(paths.db_path)
            try:
                upsert_campaign(connection, campaign, timestamp=utc_now_iso())
                seed_code_proposal_state(connection, campaign=campaign, proposal=proposal, paths=paths)
                connection.commit()
            finally:
                connection.close()

            export = run_cli("export-code-proposal", temp_root, "--proposal-id", str(proposal["proposal_id"]), "--json")
            self.assertEqual(export.returncode, 0, export.stderr)
            payload = json.loads(export.stdout)
            pack_root = Path(payload["pack_root"])

            self.assertTrue((pack_root / "proposal.json").exists())
            self.assertTrue((pack_root / "README.md").exists())
            self.assertTrue((pack_root / "acceptance_criteria.md").exists())
            self.assertTrue((pack_root / "target_files.txt").exists())
            self.assertTrue((pack_root / "return_instructions.md").exists())
            self.assertTrue((pack_root / "context" / "task_summary.json").exists())
            self.assertTrue((pack_root / "context" / "evidence.json").exists())
            self.assertTrue((pack_root / "context" / "validation_targets.json").exists())
            self.assertTrue((pack_root / "context" / "local_contracts.md").exists())
            self.assertTrue((pack_root / "context" / "proposal_context.md").exists())

            self.assertEqual(payload["evidence_count"], 2)
            self.assertEqual(payload["warning_count"], 1)

            task_summary = json.loads((pack_root / "context" / "task_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(task_summary["proposal_id"], proposal["proposal_id"])
            self.assertEqual(task_summary["target_files"], ["train.py"])
            self.assertEqual(task_summary["target_seam"], "train.py")
            self.assertEqual(task_summary["evidence_count"], 2)
            self.assertEqual(task_summary["warning_count"], 1)

            evidence = json.loads((pack_root / "context" / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["retrieval_event_id"], proposal["retrieval_event_id"])
            self.assertEqual(evidence["retrieval_query"]["query_text"], "code lane evidence lineage and validation intent")
            self.assertEqual(len(evidence["citations"]), 2)
            self.assertEqual(evidence["citations"][0]["citation_type"], "precedent")
            self.assertEqual(evidence["citations"][1]["citation_type"], "warning")
            self.assertIn("Validated lineage", evidence["citations"][0]["why_it_matters"])
            self.assertEqual(evidence["parent_validated_winners"][0]["experiment_id"], proposal["parent_ids"][0])
            self.assertEqual(evidence["parent_failures"][0]["experiment_id"], proposal["parent_ids"][1])

            validation_targets = json.loads((pack_root / "context" / "validation_targets.json").read_text(encoding="utf-8"))
            self.assertEqual(validation_targets["primary_metric"]["name"], "val_bpb")
            self.assertEqual(validation_targets["primary_metric"]["direction"], "min")
            self.assertEqual(validation_targets["expected_direction"], "improve")
            self.assertTrue(validation_targets["confirm_review_required"])
            self.assertTrue(validation_targets["audit_expected"])
            self.assertTrue(validation_targets["audit_recommended"])
            self.assertIn(proposal["parent_ids"][0], validation_targets["comparator_experiment_ids"])

            readme = (pack_root / "README.md").read_text(encoding="utf-8")
            self.assertIn("## What To Build", readme)
            self.assertIn("## Why Now", readme)
            self.assertIn("## Prior Evidence", readme)
            self.assertIn("## Allowed Files", readme)
            self.assertIn("## Success Judgment After Return", readme)
            self.assertIn("train.py", readme)

            local_contracts = (pack_root / "context" / "local_contracts.md").read_text(encoding="utf-8")
            self.assertIn("## Runner Contract", local_contracts)
            self.assertIn("## Scientific Contract", local_contracts)
            self.assertIn("## Validation Contract", local_contracts)
            self.assertIn("## File Boundary", local_contracts)

            proposal_context = (pack_root / "context" / "proposal_context.md").read_text(encoding="utf-8")
            self.assertIn("## Evidence", proposal_context)
            self.assertIn("## Validation Intent", proposal_context)
            self.assertIn(str(proposal["parent_ids"][0]), proposal_context)


if __name__ == "__main__":
    unittest.main()
