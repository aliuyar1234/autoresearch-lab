from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import PHASE6_TARGET, run_cli, target_json_command


def _write_proposal(
    root: Path,
    *,
    campaign_id: str,
    proposal_id: str,
    family: str,
    lane: str,
    overrides: dict[str, object] | None = None,
) -> Path:
    proposal_path = root / f"{proposal_id}.json"
    payload = {
        "proposal_id": proposal_id,
        "campaign_id": campaign_id,
        "lane": lane,
        "family": family,
        "kind": "structured",
        "status": "queued",
        "created_at": "2026-03-09T18:00:00Z",
        "generator": "test",
        "parent_ids": [],
        "hypothesis": f"Test proposal for {family}",
        "rationale": "Exercise report generation contracts.",
        "config_overrides": overrides or {},
        "complexity_cost": 1 if overrides else 0,
        "expected_direction": "improve",
        "tags": [family],
        "novelty_reason": None,
        "notes": None,
        "guardrails": {"max_peak_vram_gb": 92},
    }
    proposal_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return proposal_path


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


class ReportGenerationTests(unittest.TestCase):
    def _bootstrap(self, temp_root: Path) -> None:
        bootstrap = run_cli("bootstrap", temp_root, "--json")
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

    def _run_phase6_fixture(self, temp_root: Path) -> dict[str, str]:
        self._bootstrap(temp_root)
        proposal_dir = temp_root / "proposals"
        proposal_dir.mkdir(parents=True, exist_ok=True)
        baseline = _write_proposal(proposal_dir, campaign_id="base_2k", proposal_id="p_base_baseline", family="baseline", lane="scout")
        exploit = _write_proposal(
            proposal_dir,
            campaign_id="base_2k",
            proposal_id="p_base_exploit",
            family="exploit",
            lane="main",
            overrides={"optimizer_groups": {"embed_lr_scale": 1.1}},
        )
        novel = _write_proposal(
            proposal_dir,
            campaign_id="base_2k",
            proposal_id="p_base_novel",
            family="novel",
            lane="scout",
            overrides={"model": {"rope_base": 20000}},
        )

        for proposal in (baseline, exploit, novel):
            result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(proposal),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            if proposal == novel:
                self.assertEqual(result.returncode, 4, result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)

        report = run_cli("report", temp_root, "--campaign", "base_2k", "--json")
        self.assertEqual(report.returncode, 0, report.stderr)
        payload = json.loads(report.stdout)
        self.assertTrue(payload["ok"])
        return payload["artifact_paths"]

    def test_report_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._run_phase6_fixture(Path(tmpdir))
            self.assertTrue(Path(paths["report_md"]).exists())
            self.assertTrue(Path(paths["report_json"]).exists())
            self.assertTrue(Path(paths["leaderboard_md"]).exists())
            self.assertTrue(Path(paths["champion_cards_json"]).exists())
            self.assertTrue(Path(paths["crash_summary_json"]).exists())

    def test_leaderboard_campaign_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            self._run_phase6_fixture(temp_root)
            proposal_dir = temp_root / "proposals"
            stories = _write_proposal(
                proposal_dir,
                campaign_id="stories_2k",
                proposal_id="p_stories_baseline",
                family="baseline",
                lane="scout",
            )
            result = run_cli(
                "run",
                temp_root,
                "--proposal",
                str(stories),
                "--target-command-json",
                _phase6_target_command(),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = run_cli("report", temp_root, "--campaign", "base_2k", "--json")
            self.assertEqual(report.returncode, 0, report.stderr)
            report_payload = json.loads(report.stdout)
            leaderboard = json.loads(Path(report_payload["artifact_paths"]["leaderboard_json"]).read_text(encoding="utf-8"))
            self.assertTrue(leaderboard["rows"])
            self.assertTrue(all(str(row["proposal_id"]).startswith("p_base_") for row in leaderboard["rows"]))

    def test_champion_card_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._run_phase6_fixture(Path(tmpdir))
            champion_cards = json.loads(Path(paths["champion_cards_json"]).read_text(encoding="utf-8"))
            self.assertTrue(champion_cards["cards"])
            card = champion_cards["cards"][0]
            self.assertIn("experiment_id", card)
            self.assertIn("proposal_family", card)
            self.assertIn("why_it_was_better", card)

    def test_report_contains_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._run_phase6_fixture(Path(tmpdir))
            report_payload = json.loads(Path(paths["report_json"]).read_text(encoding="utf-8"))
            report_md = Path(paths["report_md"]).read_text(encoding="utf-8")
            self.assertTrue(report_payload["recommendations"]["notes"])
            self.assertIn("Next Actions", report_md)

    def test_report_starts_with_decision_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._run_phase6_fixture(Path(tmpdir))
            report_md = Path(paths["report_md"]).read_text(encoding="utf-8")
            self.assertIn("## Decision Summary", report_md)
            self.assertLess(report_md.index("## Decision Summary"), report_md.index("## Top Outcomes"))

    def test_report_exposes_trust_label_and_failure_headline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._run_phase6_fixture(Path(tmpdir))
            report_payload = json.loads(Path(paths["report_json"]).read_text(encoding="utf-8"))
            report_md = Path(paths["report_md"]).read_text(encoding="utf-8")
            current_best = report_payload["decision_summary"]["current_best_candidate"]
            self.assertIsNotNone(current_best)
            self.assertIn(current_best["trust_label"], {"provisional", "confirmed", "audited", "regressed", "invalid"})
            self.assertTrue(current_best["trust_reason"])
            first_screen = "\n".join(report_md.splitlines()[:40])
            self.assertIn("Trust label:", first_screen)
            self.assertIn("Most important failure", first_screen)
            self.assertIn("Next action:", first_screen)


if __name__ == "__main__":
    unittest.main()
