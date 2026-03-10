from __future__ import annotations

import difflib
import json
from pathlib import Path

from lab.proposals import normalize_proposal_payload
from lab.utils import utc_now_iso

from ._cli_helpers import REPO_ROOT


ROUNDTRIP_MARKER = "# code-patch roundtrip marker"


def sample_code_patch_proposal(*, proposal_id: str, lane: str = "confirm") -> dict[str, object]:
    retrieval_event_id = f"ret_{proposal_id}"
    parent_win_id = f"exp_{proposal_id}_parent_win"
    parent_fail_id = f"exp_{proposal_id}_parent_fail"
    precedent_memory_id = f"mem_{proposal_id}_precedent"
    warning_memory_id = f"mem_{proposal_id}_warning"
    created_at = utc_now_iso()
    return normalize_proposal_payload(
        {
            "proposal_id": proposal_id,
            "campaign_id": "base_2k",
            "lane": lane,
            "family": "manual",
            "kind": "code_patch",
            "status": "queued",
            "created_at": created_at,
            "generator": "human",
            "parent_ids": [parent_win_id, parent_fail_id],
            "hypothesis": "Carry code-lane evidence and validation intent all the way through execution.",
            "rationale": "The code lane should be grounded in the same memory and validation contracts as structured proposals.",
            "config_overrides": {},
            "complexity_cost": 4,
            "expected_direction": "improve",
            "tags": ["manual", "code_patch", "phase5"],
            "novelty_reason": None,
            "notes": None,
            "guardrails": {"max_peak_vram_gb": 92},
            "retrieval_event_id": retrieval_event_id,
            "evidence": [
                {
                    "memory_id": precedent_memory_id,
                    "record_type": "champion_snapshot",
                    "role": "supporting_precedent",
                    "score": 0.92,
                    "reason": "Validated lineage from an earlier winner should be preserved.",
                    "source_ref": parent_win_id,
                },
                {
                    "memory_id": warning_memory_id,
                    "record_type": "failure_autopsy",
                    "role": "warning",
                    "score": 0.74,
                    "reason": "Earlier failures lost code-lane context after import.",
                    "source_ref": parent_fail_id,
                },
            ],
            "generation_context": {
                "family_selector_reason": "manual evidence-grounded code lane task",
                "anchor_experiment_ids": [parent_win_id],
                "blocked_idea_signatures": ["blocked.phase5.dead.end"],
                "retrieval_event_id": retrieval_event_id,
                "selection_rank": 1,
                "selection_score": 0.92,
            },
            "_retrieval_event": {
                "retrieval_event_id": retrieval_event_id,
                "campaign_id": "base_2k",
                "proposal_id": proposal_id,
                "family": "manual",
                "lane": lane,
                "query_text": "code lane evidence lineage and validation intent",
                "query_tags": ["code_patch", "memory", "validation"],
                "query_payload": {"proposal_kind": "code_patch", "phase": 5},
                "items": [
                    {
                        "memory_id": precedent_memory_id,
                        "rank": 1,
                        "score": 0.92,
                        "selected_for_context": True,
                        "role_hint": "supporting_precedent",
                        "reason": "Validated winner with similar execution path",
                    },
                    {
                        "memory_id": warning_memory_id,
                        "rank": 2,
                        "score": 0.74,
                        "selected_for_context": True,
                        "role_hint": "warning",
                        "reason": "Warn against dropping import lineage",
                    },
                ],
                "created_at": created_at,
            },
            "code_patch": {
                "target_files": ["train.py"],
                "base_commit": "deadbeef",
                "patch_path": None,
                "acceptance_summary": "Keep the patch constrained while preserving export/import evidence lineage.",
                "worktree_id": None,
            },
        }
    )


def seed_code_proposal_state(connection, *, campaign: dict[str, object], proposal: dict[str, object], paths) -> None:
    created_at = str(proposal["created_at"])
    _insert_memory_record(
        connection,
        campaign=campaign,
        memory_id=str(proposal["evidence"][0]["memory_id"]),
        record_type="champion_snapshot",
        source_kind="champion",
        source_ref=str(proposal["parent_ids"][0]),
        lane=str(proposal["lane"]),
        outcome_label="promoted",
        title="Validated code-lane precedent",
        summary="A validated winner kept code-lane lineage intact.",
        tags=["precedent", "validated", "code_patch"],
        payload={"experiment_id": str(proposal["parent_ids"][0]), "validation_state": "passed"},
        created_at=created_at,
    )
    _insert_memory_record(
        connection,
        campaign=campaign,
        memory_id=str(proposal["evidence"][1]["memory_id"]),
        record_type="failure_autopsy",
        source_kind="experiment",
        source_ref=str(proposal["parent_ids"][1]),
        lane=str(proposal["lane"]),
        outcome_label="failed",
        title="Code-lane warning",
        summary="A prior attempt lost evidence context during import.",
        tags=["warning", "failure", "code_patch"],
        payload={"experiment_id": str(proposal["parent_ids"][1]), "crash_class": "assertion_failure"},
        created_at=created_at,
    )
    connection.execute(
        """
        INSERT INTO proposals (
            proposal_id, campaign_id, family, kind, lane, status, generator, parent_ids_json,
            complexity_cost, hypothesis, rationale, config_overrides_json, retrieval_event_id,
            idea_signature, mutation_paths_json, proposal_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(proposal_id) DO UPDATE SET
            proposal_json=excluded.proposal_json,
            retrieval_event_id=excluded.retrieval_event_id,
            updated_at=excluded.updated_at
        """,
        (
            proposal["proposal_id"],
            proposal["campaign_id"],
            proposal["family"],
            proposal["kind"],
            proposal["lane"],
            proposal["status"],
            proposal["generator"],
            json.dumps(proposal["parent_ids"], sort_keys=True),
            proposal["complexity_cost"],
            proposal["hypothesis"],
            proposal["rationale"],
            json.dumps(proposal["config_overrides"], sort_keys=True),
            proposal["retrieval_event_id"],
            proposal["idea_signature"],
            json.dumps(proposal["mutation_paths"], sort_keys=True),
            json.dumps({key: value for key, value in proposal.items() if key != "_retrieval_event"}, sort_keys=True),
            created_at,
            created_at,
        ),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO retrieval_events (
            retrieval_event_id, campaign_id, proposal_id, family, lane, query_text,
            query_tags_json, query_payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposal["_retrieval_event"]["retrieval_event_id"],
            proposal["_retrieval_event"]["campaign_id"],
            proposal["_retrieval_event"]["proposal_id"],
            proposal["_retrieval_event"]["family"],
            proposal["_retrieval_event"]["lane"],
            proposal["_retrieval_event"]["query_text"],
            json.dumps(proposal["_retrieval_event"]["query_tags"], sort_keys=True),
            json.dumps(proposal["_retrieval_event"]["query_payload"], sort_keys=True),
            proposal["_retrieval_event"]["created_at"],
        ),
    )
    connection.execute("DELETE FROM retrieval_event_items WHERE retrieval_event_id = ?", (proposal["retrieval_event_id"],))
    for item in proposal["_retrieval_event"]["items"]:
        connection.execute(
            """
            INSERT INTO retrieval_event_items (
                retrieval_event_id, memory_id, rank, score, selected_for_context, role_hint, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal["retrieval_event_id"],
                item["memory_id"],
                item["rank"],
                item["score"],
                1 if item["selected_for_context"] else 0,
                item["role_hint"],
                item["reason"],
                proposal["_retrieval_event"]["created_at"],
            ),
        )
    connection.execute("DELETE FROM proposal_evidence_links WHERE proposal_id = ?", (proposal["proposal_id"],))
    for item in proposal["evidence"]:
        connection.execute(
            """
            INSERT INTO proposal_evidence_links (
                proposal_id, memory_id, retrieval_event_id, role, score, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal["proposal_id"],
                item["memory_id"],
                proposal["retrieval_event_id"],
                item["role"],
                item["score"],
                item["reason"],
                created_at,
            ),
        )
    _insert_experiment(
        connection,
        experiment_id=str(proposal["parent_ids"][0]),
        proposal_id=str(proposal["proposal_id"]),
        lane=str(proposal["lane"]),
        status="completed",
        disposition="promoted",
        validation_state="passed",
        metric=0.944,
        artifact_root=Path(paths.runs_root) / str(proposal["parent_ids"][0]),
        idea_signature=str(proposal["idea_signature"]),
        started_at=created_at,
        ended_at=created_at,
    )
    _insert_experiment(
        connection,
        experiment_id=str(proposal["parent_ids"][1]),
        proposal_id=str(proposal["proposal_id"]),
        lane=str(proposal["lane"]),
        status="failed",
        disposition="discarded",
        validation_state="failed",
        metric=None,
        artifact_root=Path(paths.runs_root) / str(proposal["parent_ids"][1]),
        idea_signature=str(proposal["idea_signature"]),
        started_at=created_at,
        ended_at=created_at,
        crash_class="assertion_failure",
    )


def build_train_patch() -> str:
    original = (REPO_ROOT / "train.py").read_text(encoding="utf-8").splitlines(keepends=True)
    modified = original + [ROUNDTRIP_MARKER + "\n"]
    return "".join(
        difflib.unified_diff(
            original,
            modified,
            fromfile="a/train.py",
            tofile="b/train.py",
            n=3,
        )
    )


def _insert_memory_record(
    connection,
    *,
    campaign: dict[str, object],
    memory_id: str,
    record_type: str,
    source_kind: str,
    source_ref: str,
    title: str,
    summary: str,
    tags: list[str],
    payload: dict[str, object],
    created_at: str,
    lane: str | None = None,
    outcome_label: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO memory_records (
            memory_id, campaign_id, comparability_group, record_type, source_kind, source_ref,
            family, lane, eval_split, outcome_label, title, summary, tags_json, payload_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            memory_id,
            "base_2k",
            campaign.get("comparability_group"),
            record_type,
            source_kind,
            source_ref,
            "manual",
            lane,
            "search_val",
            outcome_label,
            title,
            summary,
            json.dumps(tags, sort_keys=True),
            json.dumps(payload, sort_keys=True),
            created_at,
            created_at,
        ),
    )


def _insert_experiment(
    connection,
    *,
    experiment_id: str,
    proposal_id: str,
    lane: str,
    status: str,
    disposition: str,
    validation_state: str,
    metric: float | None,
    artifact_root: Path,
    idea_signature: str | None,
    started_at: str,
    ended_at: str,
    crash_class: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO experiments (
            experiment_id, proposal_id, campaign_id, lane, status, eval_split, run_purpose,
            replay_source_experiment_id, validation_state, validation_review_id, idea_signature,
            disposition, crash_class, seed, git_commit, device_profile, backend, proposal_family,
            proposal_kind, complexity_cost, budget_seconds, primary_metric_name, primary_metric_value,
            metric_delta, tokens_per_second, peak_vram_gb, summary_path, artifact_root,
            started_at, ended_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            experiment_id,
            proposal_id,
            "base_2k",
            lane,
            status,
            "search_val",
            "search",
            None,
            validation_state,
            None,
            idea_signature,
            disposition,
            crash_class,
            42,
            "deadbeef",
            "test_profile",
            "test_backend",
            "manual",
            "code_patch",
            4,
            300,
            "val_bpb",
            metric,
            None,
            2048.0,
            1.2,
            str(artifact_root / "summary.json"),
            str(artifact_root),
            started_at,
            ended_at,
            started_at,
            ended_at,
        ),
    )
