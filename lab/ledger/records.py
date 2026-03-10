from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..proposals import normalize_proposal_payload


def campaign_row_from_manifest(manifest: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
    return {
        "campaign_id": manifest["campaign_id"],
        "version": manifest["version"],
        "title": manifest["title"],
        "active": 1 if manifest["active"] else 0,
        "comparability_group": manifest["comparability_group"],
        "primary_metric_name": manifest["primary_metric"]["name"],
        "manifest_json": json.dumps(manifest, sort_keys=True),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def proposal_row_from_payload(payload: dict[str, Any], *, updated_at: str | None = None) -> dict[str, Any]:
    normalized = normalize_proposal_payload(payload)
    for key in ("_retrieval_event", "priority_hint", "validated_anchor_quality", "novelty_score"):
        normalized.pop(key, None)
    return {
        "proposal_id": normalized["proposal_id"],
        "campaign_id": normalized["campaign_id"],
        "family": normalized["family"],
        "kind": normalized["kind"],
        "lane": normalized["lane"],
        "status": normalized["status"],
        "generator": normalized["generator"],
        "parent_ids_json": json.dumps(normalized.get("parent_ids", []), sort_keys=True),
        "complexity_cost": normalized["complexity_cost"],
        "hypothesis": normalized["hypothesis"],
        "rationale": normalized["rationale"],
        "config_overrides_json": json.dumps(normalized.get("config_overrides", {}), sort_keys=True),
        "retrieval_event_id": normalized.get("retrieval_event_id"),
        "idea_signature": normalized.get("idea_signature"),
        "mutation_paths_json": json.dumps(normalized.get("mutation_paths", []), sort_keys=True),
        "proposal_json": json.dumps(normalized, sort_keys=True),
        "created_at": normalized["created_at"],
        "updated_at": updated_at or normalized.get("updated_at", normalized["created_at"]),
    }


def experiment_row_from_summary(
    summary: dict[str, Any],
    *,
    artifact_root: Path,
    disposition: str | None = None,
    crash_class: str | None = None,
) -> dict[str, Any]:
    return {
        "experiment_id": summary["experiment_id"],
        "proposal_id": summary.get("proposal_id"),
        "campaign_id": summary["campaign_id"],
        "lane": summary["lane"],
        "status": summary["status"],
        "eval_split": summary.get("eval_split", "search_val"),
        "run_purpose": summary.get("run_purpose", "search"),
        "replay_source_experiment_id": summary.get("replay_source_experiment_id"),
        "validation_state": summary.get("validation_state", "not_required"),
        "validation_review_id": summary.get("validation_review_id"),
        "idea_signature": summary.get("idea_signature"),
        "disposition": disposition if disposition is not None else summary.get("disposition"),
        "crash_class": crash_class if crash_class is not None else summary.get("crash_class"),
        "seed": summary["seed"],
        "git_commit": summary["git_commit"],
        "device_profile": summary["device_profile"],
        "backend": summary["backend"],
        "proposal_family": summary.get("proposal_family"),
        "proposal_kind": summary.get("proposal_kind"),
        "complexity_cost": summary.get("complexity_cost"),
        "budget_seconds": summary["budget_seconds"],
        "primary_metric_name": summary["primary_metric_name"],
        "primary_metric_value": summary["primary_metric_value"],
        "metric_delta": summary.get("metric_delta"),
        "tokens_per_second": summary["tokens_per_second"],
        "peak_vram_gb": summary["peak_vram_gb"],
        "summary_path": str(Path(artifact_root) / "summary.json"),
        "artifact_root": str(artifact_root),
        "started_at": summary.get("started_at"),
        "ended_at": summary.get("ended_at"),
        "created_at": summary.get("started_at") or summary.get("ended_at"),
        "updated_at": summary.get("ended_at") or summary.get("started_at"),
    }


def validation_review_row_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": payload["review_id"],
        "source_experiment_id": payload["source_experiment_id"],
        "campaign_id": payload["campaign_id"],
        "review_type": payload["review_type"],
        "eval_split": payload["eval_split"],
        "candidate_experiment_ids_json": json.dumps(payload.get("candidate_experiment_ids", []), sort_keys=True),
        "comparator_experiment_ids_json": json.dumps(payload.get("comparator_experiment_ids", []), sort_keys=True),
        "seed_list_json": json.dumps(payload.get("seed_list", []), sort_keys=True),
        "candidate_metric_median": payload.get("candidate_metric_median"),
        "comparator_metric_median": payload.get("comparator_metric_median"),
        "delta_median": payload.get("delta_median"),
        "decision": payload["decision"],
        "reason": payload["reason"],
        "review_json": json.dumps(payload.get("review", {}), sort_keys=True),
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
    }


def artifact_rows_from_index(index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    experiment_id = index_payload["experiment_id"]
    rows: list[dict[str, Any]] = []
    for artifact in index_payload["artifacts"]:
        row = dict(artifact)
        row["experiment_id"] = experiment_id
        rows.append(row)
    return rows
