from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lab.ledger.db import apply_migrations, connect


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_TOOL = REPO_ROOT / "tools" / "verify_showcase_bundle.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_verifier(showcase_root: Path, db_path: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else os.pathsep.join([str(REPO_ROOT), existing_pythonpath])
    return subprocess.run(
        [
            sys.executable,
            str(VERIFY_TOOL),
            "--showcase-root",
            str(showcase_root),
            "--db-path",
            str(db_path),
            "--json",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_bundle(root: Path) -> tuple[Path, Path]:
    showcase_root = root / "showcase_bundle"
    db_path = root / "lab.sqlite3"
    timestamp = "2026-03-11T12:00:00+00:00"

    apply_migrations(db_path, REPO_ROOT / "sql")
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO campaigns (
                campaign_id, version, title, active, comparability_group, primary_metric_name,
                manifest_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "base_2k",
                "1",
                "Base 2k",
                1,
                "dense-gpt-single-gpu",
                "val_loss",
                json.dumps({"campaign_id": "base_2k"}, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        for proposal_id, family, lane, retrieval_event_id in (
            ("prop_confirmed", "exploit", "main", "retr_1"),
            ("prop_provisional", "baseline", "scout", None),
            ("prop_replay", "replay", "main", None),
        ):
            proposal_payload = {
                "proposal_id": proposal_id,
                "campaign_id": "base_2k",
                "family": family,
                "kind": "config",
                "lane": lane,
                "generator": "fixture",
                "parent_ids": [],
                "complexity_cost": 0,
                "hypothesis": "fixture",
                "rationale": "fixture",
                "config_overrides": {},
                "retrieval_event_id": retrieval_event_id,
                "evidence": [{"memory_id": "mem_1", "role": "support"}] if retrieval_event_id else [],
                "generation_context": {"anchor_experiment_ids": []},
            }
            connection.execute(
                """
                INSERT INTO proposals (
                    proposal_id, campaign_id, family, kind, lane, status, generator,
                    parent_ids_json, complexity_cost, hypothesis, rationale,
                    config_overrides_json, proposal_json, retrieval_event_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    "base_2k",
                    family,
                    "config",
                    lane,
                    "completed",
                    "fixture",
                    "[]",
                    0,
                    "fixture",
                    "fixture",
                    "{}",
                    json.dumps(proposal_payload, sort_keys=True),
                    retrieval_event_id,
                    timestamp,
                    timestamp,
                ),
            )

        workspace_root = showcase_root / "pair_01"
        remembering_root = workspace_root / "remembering"
        amnesiac_root = workspace_root / "amnesiac"
        replay_root = remembering_root / "replays" / "exp_replay"
        report_root = remembering_root / "reports"
        artifacts_root = remembering_root / "artifacts"
        amnesiac_artifacts_root = amnesiac_root / "artifacts"

        summary_confirmed = artifacts_root / "runs" / "exp_confirmed" / "summary.json"
        summary_provisional = amnesiac_artifacts_root / "runs" / "exp_provisional" / "summary.json"
        summary_replay = replay_root / "summary.json"
        for path in (summary_confirmed, summary_provisional, summary_replay):
            _write_json(path, {"ok": True, "path": str(path)})

        experiments = [
            (
                "exp_confirmed",
                "prop_confirmed",
                "main",
                "completed",
                "promote",
                None,
                artifacts_root / "runs" / "exp_confirmed",
                summary_confirmed,
                "search_val",
                "search",
                "passed",
                "rev_confirm",
                None,
                0.75,
            ),
            (
                "exp_provisional",
                "prop_provisional",
                "scout",
                "completed",
                "keep",
                None,
                amnesiac_artifacts_root / "runs" / "exp_provisional",
                summary_provisional,
                "search_val",
                "search",
                "not_required",
                None,
                None,
                0.9,
            ),
            (
                "exp_replay",
                "prop_replay",
                "main",
                "completed",
                "keep",
                None,
                replay_root,
                summary_replay,
                "locked_val",
                "replay",
                "not_required",
                None,
                "exp_confirmed",
                0.7,
            ),
        ]
        for (
            experiment_id,
            proposal_id,
            lane,
            status,
            disposition,
            crash_class,
            artifact_root,
            summary_path,
            eval_split,
            run_purpose,
            validation_state,
            validation_review_id,
            replay_source_experiment_id,
            metric,
        ) in experiments:
            connection.execute(
                """
                INSERT INTO experiments (
                    experiment_id, proposal_id, campaign_id, lane, status, disposition, crash_class,
                    seed, git_commit, device_profile, backend, proposal_family, proposal_kind,
                    complexity_cost, budget_seconds, primary_metric_name, primary_metric_value,
                    metric_delta, tokens_per_second, peak_vram_gb, summary_path, artifact_root,
                    started_at, ended_at, created_at, updated_at, eval_split, run_purpose,
                    replay_source_experiment_id, validation_state, validation_review_id, idea_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    proposal_id,
                    "base_2k",
                    lane,
                    status,
                    disposition,
                    crash_class,
                    42,
                    "deadbeef",
                    "single-gpu",
                    "eager",
                    "exploit" if proposal_id == "prop_confirmed" else "baseline",
                    "config",
                    0,
                    300,
                    "val_loss",
                    metric,
                    None,
                    1.0,
                    1.0,
                    str(summary_path),
                    str(artifact_root),
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                    eval_split,
                    run_purpose,
                    replay_source_experiment_id,
                    validation_state,
                    validation_review_id,
                    f"sig_{proposal_id}",
                ),
            )

        connection.execute(
            """
            INSERT INTO validation_reviews (
                review_id, source_experiment_id, campaign_id, review_type, eval_split,
                candidate_experiment_ids_json, comparator_experiment_ids_json, seed_list_json,
                candidate_metric_median, comparator_metric_median, delta_median, decision, reason,
                review_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rev_confirm",
                "exp_confirmed",
                "base_2k",
                "confirm",
                "search_val",
                json.dumps(["exp_confirmed"]),
                json.dumps(["exp_provisional"]),
                json.dumps([42]),
                0.75,
                0.9,
                -0.15,
                "passed",
                "fixture",
                json.dumps({"review_id": "rev_confirm"}, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO memory_records (
                memory_id, campaign_id, comparability_group, record_type, source_kind, source_ref,
                family, lane, eval_split, outcome_label, title, summary, tags_json, payload_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mem_1",
                "base_2k",
                "dense-gpt-single-gpu",
                "validated_winner",
                "experiment",
                "exp_confirmed",
                "exploit",
                "main",
                "search_val",
                "confirmed",
                "fixture memory",
                "fixture memory",
                json.dumps(["fixture"]),
                json.dumps({"experiment_id": "exp_confirmed"}, sort_keys=True),
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO retrieval_events (
                retrieval_event_id, campaign_id, proposal_id, family, lane, query_text,
                query_tags_json, query_payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "retr_1",
                "base_2k",
                "prop_confirmed",
                "exploit",
                "main",
                "fixture query",
                json.dumps(["fixture"]),
                json.dumps({"campaign_id": "base_2k"}, sort_keys=True),
                timestamp,
            ),
        )
        connection.commit()

    run_manifest_path = showcase_root / "pair_01" / "remembering" / "run_manifest.json"
    amnesiac_run_manifest_path = showcase_root / "pair_01" / "amnesiac" / "run_manifest.json"
    remembering_candidate_summary_path = showcase_root / "pair_01" / "remembering" / "candidate_summary.json"
    amnesiac_candidate_summary_path = showcase_root / "pair_01" / "amnesiac" / "candidate_summary.json"
    leaderboard_snapshot_path = showcase_root / "pair_01" / "remembering" / "leaderboard_snapshot.json"
    archive_snapshot_path = showcase_root / "pair_01" / "remembering" / "archive_snapshot.json"
    report_json_path = showcase_root / "pair_01" / "remembering" / "reports" / "report.json"
    candidate_summary_root_path = showcase_root / "candidate_summary.json"
    confirm_comparison_path = showcase_root / "validations" / "confirm_comparison.json"
    audit_comparison_path = showcase_root / "validations" / "audit_comparison.json"
    clean_replays_path = showcase_root / "validations" / "clean_replays.json"
    candidate_pool_path = showcase_root / "validations" / "candidate_pool.json"

    for path in (
        run_manifest_path,
        amnesiac_run_manifest_path,
        remembering_candidate_summary_path,
        amnesiac_candidate_summary_path,
        leaderboard_snapshot_path,
        archive_snapshot_path,
        report_json_path,
    ):
        _write_json(path, {"ok": True, "path": str(path)})
    (showcase_root / "pair_01" / "amnesiac" / "reports").mkdir(parents=True, exist_ok=True)

    compare_payload = {
        "campaign_id": "base_2k",
        "candidate_summary_path": str(candidate_summary_root_path),
        "pairs": [
            {
                "pair_id": "pair_01",
                "order": ["remembering", "amnesiac"],
                "winner_by_best_raw_metric": "remembering",
                "arms": {
                    "remembering": {
                        "arm": "remembering",
                        "db_path": str(db_path),
                        "workspace_root": str(showcase_root / "pair_01" / "remembering"),
                        "artifacts_root": str(showcase_root / "pair_01" / "remembering" / "artifacts"),
                        "run_manifest_path": str(run_manifest_path),
                        "candidate_summary_path": str(remembering_candidate_summary_path),
                        "leaderboard_snapshot_path": str(leaderboard_snapshot_path),
                        "archive_snapshot_path": str(archive_snapshot_path),
                        "report_paths": {"report_json": str(report_json_path)},
                        "session": {
                            "run_count": 1,
                            "executed": [
                                {
                                    "experiment_id": "exp_confirmed",
                                    "proposal_id": "prop_confirmed",
                                }
                            ],
                            "report": {
                                "report_root": str(showcase_root / "pair_01" / "remembering" / "reports"),
                                "promoted_count": 1,
                                "failed_count": 0,
                                "current_best_candidate": {
                                    "experiment_id": "exp_confirmed",
                                    "proposal_id": "prop_confirmed",
                                    "trust_label": "confirmed",
                                    "validation_review_id": "rev_confirm",
                                },
                                "memory_citation_coverage": 1.0,
                                "repeated_dead_end_rate": 0.0,
                            },
                        },
                        "best_candidate": {
                            "experiment_id": "exp_confirmed",
                            "proposal_id": "prop_confirmed",
                            "primary_metric_value": 0.75,
                            "trust_label": "confirmed",
                            "validation_review_id": "rev_confirm",
                        },
                    },
                    "amnesiac": {
                        "arm": "amnesiac",
                        "db_path": str(db_path),
                        "workspace_root": str(showcase_root / "pair_01" / "amnesiac"),
                        "artifacts_root": str(showcase_root / "pair_01" / "amnesiac" / "artifacts"),
                        "run_manifest_path": str(amnesiac_run_manifest_path),
                        "candidate_summary_path": str(amnesiac_candidate_summary_path),
                        "leaderboard_snapshot_path": None,
                        "archive_snapshot_path": None,
                        "report_paths": {},
                        "session": {
                            "run_count": 1,
                            "executed": [
                                {
                                    "experiment_id": "exp_provisional",
                                    "proposal_id": "prop_provisional",
                                }
                            ],
                            "report": {
                                "report_root": str(showcase_root / "pair_01" / "amnesiac" / "reports"),
                                "promoted_count": 0,
                                "failed_count": 0,
                                "current_best_candidate": {
                                    "experiment_id": "exp_provisional",
                                    "proposal_id": "prop_provisional",
                                    "trust_label": "provisional",
                                },
                                "memory_citation_coverage": 0.0,
                                "repeated_dead_end_rate": 0.1,
                            },
                        },
                        "best_candidate": {
                            "experiment_id": "exp_provisional",
                            "proposal_id": "prop_provisional",
                            "primary_metric_value": 0.9,
                            "trust_label": "provisional",
                        },
                    },
                },
            }
        ],
        "aggregate": {"pair_count": 1},
    }
    _write_json(showcase_root / "compare.json", compare_payload)

    _write_json(
        candidate_summary_root_path,
        {
            "campaign_id": "base_2k",
            "pairs": ["pair_01"],
            "top_candidates_by_arm": {
                "remembering": [
                    {
                        "pair_id": "pair_01",
                        "experiment_id": "exp_confirmed",
                        "proposal_id": "prop_confirmed",
                        "retrieval_event_id": "retr_1",
                        "evidence_memory_ids": ["mem_1"],
                    }
                ],
                "amnesiac": [
                    {
                        "pair_id": "pair_01",
                        "experiment_id": "exp_provisional",
                        "proposal_id": "prop_provisional",
                        "retrieval_event_id": None,
                        "evidence_memory_ids": [],
                    }
                ],
            },
        },
    )

    _write_json(candidate_pool_path, {"remembering": [], "amnesiac": []})
    _write_json(
        confirm_comparison_path,
        {
            "arms": {
                "remembering": {
                    "reviews": [
                        {
                            "review_id": "rev_confirm",
                            "source_experiment_id": "exp_confirmed",
                        }
                    ]
                }
            }
        },
    )
    _write_json(audit_comparison_path, {"arms": {"remembering": {"status": "data_missing"}}})
    _write_json(
        clean_replays_path,
        {
            "baseline": {"status": "data_missing"},
            "remembering": {
                "source_experiment_id": "exp_confirmed",
                "replay_experiment_id": "exp_replay",
                "summary_path": str(showcase_root / "pair_01" / "remembering" / "replays" / "exp_replay" / "summary.json"),
                "artifact_root": str(showcase_root / "pair_01" / "remembering" / "replays" / "exp_replay"),
                "run_purpose": "replay",
            },
            "amnesiac": {"status": "data_missing"},
        },
    )
    _write_json(
        showcase_root / "validations" / "validation_summary.json",
        {
            "ok": True,
            "campaign_id": "base_2k",
            "candidate_pool_path": str(candidate_pool_path),
            "confirm_comparison_path": str(confirm_comparison_path),
            "audit_comparison_path": str(audit_comparison_path),
            "clean_replays_path": str(clean_replays_path),
            "final_primary_comparison": {
                "remembering": {
                    "review_id": "rev_confirm",
                    "source_experiment_id": "exp_confirmed",
                },
                "amnesiac": None,
            },
            "final_audit_comparison": {
                "remembering": {"status": "data_missing"},
                "amnesiac": {"status": "data_missing"},
            },
            "memory_citation_examples": [
                {
                    "arm": "remembering",
                    "experiment_id": "exp_confirmed",
                    "retrieval_event_id": "retr_1",
                    "evidence_count": 1,
                    "evidence_memory_ids": ["mem_1"],
                }
            ],
            "candidate_lineage_references": [
                {
                    "pair_id": "pair_01",
                    "arm": "remembering",
                    "experiment_id": "exp_confirmed",
                    "proposal_id": "prop_confirmed",
                    "parent_ids": [],
                    "evidence_memory_ids": ["mem_1"],
                    "retrieval_event_id": "retr_1",
                }
            ],
            "repeated_dead_end_metrics": {"remembering": 0.0, "amnesiac": 0.1},
        },
    )
    return showcase_root, db_path


class ShowcaseVerifyBundleTests(unittest.TestCase):
    def test_verifier_passes_on_coherent_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            showcase_root, db_path = _seed_bundle(Path(tmpdir))
            result = _run_verifier(showcase_root, db_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["missing_rows"], [])
            self.assertEqual(payload["missing_files"], [])
            self.assertEqual(payload["trust_mismatches"], [])

    def test_verifier_fails_on_missing_referenced_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            showcase_root, db_path = _seed_bundle(Path(tmpdir))
            compare_path = showcase_root / "compare.json"
            compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))
            compare_payload["pairs"][0]["arms"]["remembering"]["best_candidate"]["experiment_id"] = "exp_missing"
            compare_path.write_text(json.dumps(compare_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = _run_verifier(showcase_root, db_path)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any(item["value"] == "exp_missing" for item in payload["missing_rows"]))


if __name__ == "__main__":
    unittest.main()
