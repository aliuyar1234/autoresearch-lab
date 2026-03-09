from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
    return {
        "proposal_id": payload["proposal_id"],
        "campaign_id": payload["campaign_id"],
        "family": payload["family"],
        "kind": payload["kind"],
        "lane": payload["lane"],
        "status": payload["status"],
        "generator": payload["generator"],
        "parent_ids_json": json.dumps(payload.get("parent_ids", []), sort_keys=True),
        "complexity_cost": payload["complexity_cost"],
        "hypothesis": payload["hypothesis"],
        "rationale": payload["rationale"],
        "config_overrides_json": json.dumps(payload.get("config_overrides", {}), sort_keys=True),
        "proposal_json": json.dumps(payload, sort_keys=True),
        "created_at": payload["created_at"],
        "updated_at": updated_at or payload.get("updated_at", payload["created_at"]),
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


def artifact_rows_from_index(index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    experiment_id = index_payload["experiment_id"]
    rows: list[dict[str, Any]] = []
    for artifact in index_payload["artifacts"]:
        row = dict(artifact)
        row["experiment_id"] = experiment_id
        rows.append(row)
    return rows
