from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import PHASE6_TARGET, SAMPLE_PROPOSAL, run_cli, target_json_command


REPO_ROOT = Path(__file__).resolve().parents[2]
SHOWCASE_ROOT = REPO_ROOT / "showcase" / "the-remembering-scientist"


def _write_proposal(
    root: Path,
    *,
    proposal_id: str,
    family: str,
    lane: str,
    overrides: dict[str, object] | None = None,
) -> Path:
    payload = json.loads(SAMPLE_PROPOSAL.read_text(encoding="utf-8"))
    payload["proposal_id"] = proposal_id
    payload["lane"] = lane
    payload["family"] = family
    payload["parent_ids"] = []
    payload["source_experiments"] = []
    payload["config_overrides"] = overrides or {}
    payload["complexity_cost"] = 0 if family == "baseline" else 1
    payload["idea_signature"] = f"sig_{proposal_id}"
    payload["mutation_paths"] = list(_mutation_paths(overrides))
    payload["generation_context"] = {
        "family_selector_reason": "showcase scaffold fixture",
        "anchor_experiment_ids": [],
        "blocked_idea_signatures": [],
        "retrieval_event_id": None,
        "selection_rank": 1,
        "selection_score": 1.0,
    }
    proposal_path = root / f"{proposal_id}.json"
    proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proposal_path


def _mutation_paths(overrides: dict[str, object] | None) -> list[str]:
    if not overrides:
        return []
    paths: list[str] = []

    def visit(prefix: str, value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(f"{prefix}.{key}" if prefix else str(key), nested)
            return
        paths.append(prefix)

    visit("", overrides)
    return [path for path in paths if path]


def _phase6_command() -> str:
    return target_json_command(
        [
            sys.executable,
            str(PHASE6_TARGET),
            "--summary-out",
            "{summary_out}",
            "--config-path",
            "{config_path}",
            "--experiment-id",
            "{experiment_id}",
            "--proposal-id",
            "{proposal_id}",
            "--campaign-id",
            "{campaign_id}",
            "--lane",
            "{lane}",
            "--eval-split",
            "{eval_split}",
            "--run-purpose",
            "{run_purpose}",
            "--backend",
            "{backend}",
            "--device-profile",
            "{device_profile}",
            "--repo-root",
            "{repo_root}",
            "--artifacts-root",
            "{artifacts_root}",
            "--cache-root",
            "{cache_root}",
            "--seed",
            "{seed}",
            "--time-budget-seconds",
            "{time_budget_seconds}",
        ]
    )


def _run_showcase_script(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else os.pathsep.join([str(REPO_ROOT), existing_pythonpath])
    return subprocess.run(
        [sys.executable, str(SHOWCASE_ROOT / script_name), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ShowcaseCompareJsonScaffoldTests(unittest.TestCase):
    def test_showcase_pipeline_generates_compare_validation_and_render_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "seed_source"
            showcase_output_root = root / "showcase_output"
            snapshot_root = root / "seed_snapshot"
            proposal_root = root / "seed_proposals"
            proposal_root.mkdir(parents=True, exist_ok=True)

            bootstrap = run_cli("bootstrap", source_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            proposals = [
                _write_proposal(proposal_root, proposal_id="p_showcase_baseline", family="baseline", lane="scout"),
                _write_proposal(
                    proposal_root,
                    proposal_id="p_showcase_exploit",
                    family="exploit",
                    lane="main",
                    overrides={"optimizer_groups": {"embed_lr_scale": 1.1}},
                ),
                _write_proposal(
                    proposal_root,
                    proposal_id="p_showcase_combine",
                    family="combine",
                    lane="main",
                    overrides={"model": {"qkv_bias": False}},
                ),
            ]

            for proposal_path in proposals:
                run = run_cli(
                    "run",
                    source_root,
                    "--proposal",
                    str(proposal_path),
                    "--target-command-json",
                    _phase6_command(),
                    "--json",
                )
                self.assertEqual(run.returncode, 0, run.stderr)

            report = run_cli("report", source_root, "--campaign", "base_2k", "--json")
            self.assertEqual(report.returncode, 0, report.stderr)

            freeze = _run_showcase_script(
                "freeze_memory_snapshot.py",
                "--campaign",
                "base_2k",
                "--source-db",
                str(source_root / "lab.sqlite3"),
                "--output-root",
                str(snapshot_root),
            )
            self.assertEqual(freeze.returncode, 0, freeze.stderr)
            freeze_payload = json.loads(freeze.stdout)
            self.assertTrue(freeze_payload["ok"])
            self.assertTrue((snapshot_root / "MANIFEST.json").exists())
            self.assertTrue((snapshot_root / "MANIFEST.md").exists())
            manifest = json.loads((snapshot_root / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertGreater(manifest["counts"]["experiments"], 0)
            self.assertGreater(manifest["counts"]["memory_records"], 0)

            compare = _run_showcase_script(
                "run_ab_test.py",
                "--campaign",
                "base_2k",
                "--output-root",
                str(showcase_output_root),
                "--snapshot-root",
                str(snapshot_root),
                "--pairs",
                "1",
                "--hours",
                "0",
                "--max-runs",
                "3",
                "--no-allow-confirm",
                "--target-command-json",
                _phase6_command(),
            )
            self.assertEqual(compare.returncode, 0, compare.stderr)
            compare_payload = json.loads(compare.stdout)
            self.assertEqual(compare_payload["aggregate"]["pair_count"], 1)
            self.assertTrue((showcase_output_root / "compare.json").exists())
            self.assertTrue((showcase_output_root / "compare.md").exists())
            self.assertTrue((showcase_output_root / "candidate_summary.json").exists())

            pair = compare_payload["pairs"][0]
            for arm_name in ("remembering", "amnesiac"):
                arm = pair["arms"][arm_name]
                self.assertGreater(arm["session"]["run_count"], 0)
                self.assertTrue(Path(arm["run_manifest_path"]).exists())
                self.assertTrue(Path(arm["candidate_summary_path"]).exists())

            validations = _run_showcase_script(
                "run_validations.py",
                "--campaign",
                "base_2k",
                "--output-root",
                str(showcase_output_root),
                "--top-per-arm",
                "1",
                "--time-budget-seconds",
                "5",
                "--target-command-json",
                _phase6_command(),
            )
            self.assertEqual(validations.returncode, 0, validations.stderr)
            validation_payload = json.loads(validations.stdout)
            self.assertTrue(validation_payload["ok"])
            for name in (
                "candidate_pool.json",
                "confirm_comparison.json",
                "audit_comparison.json",
                "clean_replays.json",
                "validation_summary.json",
            ):
                self.assertTrue((showcase_output_root / "validations" / name).exists(), name)

            render = _run_showcase_script(
                "render_case_study.py",
                "--campaign",
                "base_2k",
                "--output-root",
                str(showcase_output_root),
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            render_payload = json.loads(render.stdout)
            self.assertTrue(render_payload["ok"])

            for name in (
                "hero_curve.json",
                "morning_report_comparison.json",
                "retrieval_panels.json",
                "lineage_graph.json",
                "audit_panel.json",
                "repeated_dead_end.json",
            ):
                figure_path = showcase_output_root / "figures" / name
                self.assertTrue(figure_path.exists(), name)
                payload = json.loads(figure_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "ready")

            draft_path = showcase_output_root / "CASE_STUDY_DRAFT.md"
            self.assertTrue(draft_path.exists())
            draft_text = draft_path.read_text(encoding="utf-8")
            self.assertIn("A/B Summary", draft_text)
            self.assertIn("Validation Summary", draft_text)


if __name__ == "__main__":
    unittest.main()
