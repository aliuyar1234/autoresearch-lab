from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reference_impl.archive_policy import RunRecord, archive_buckets

from ..paths import LabPaths
from ..utils import utc_now_iso, write_json
from .novelty import novelty_tags


def build_archive_snapshot(experiments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    runs: list[RunRecord] = []
    for row in experiments:
        if row.get("status") is not None and str(row.get("status")) != "completed":
            continue
        metric_value = row.get("primary_metric_value")
        if metric_value is None:
            continue
        proposal_payload = _proposal_payload(row)
        runs.append(
            RunRecord(
                experiment_id=str(row["experiment_id"]),
                metric_value=float(metric_value),
                peak_vram_gb=float(row.get("peak_vram_gb") or 0.0),
                complexity_cost=int(row.get("complexity_cost") or 0),
                novelty_tags=novelty_tags(proposal_payload.get("config_overrides", {})),
                disposition=str(row.get("disposition") or "discarded"),
                lane=str(row["lane"]),
            )
        )
    buckets = archive_buckets(runs)
    return {
        name: [_run_record_to_dict(item) for item in items]
        for name, items in buckets.items()
    }


def archive_snapshot_document(*, campaign_id: str, snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "updated_at": utc_now_iso(),
        "buckets": snapshot,
    }


def write_archive_snapshot(paths: LabPaths, campaign_id: str, snapshot: dict[str, list[dict[str, Any]]]) -> Path:
    archive_dir = paths.archive_root / campaign_id
    document = archive_snapshot_document(campaign_id=campaign_id, snapshot=snapshot)
    write_json(archive_dir / "archive_snapshot.json", document)
    (archive_dir / "archive_summary.md").write_text(_render_archive_markdown(document), encoding="utf-8")
    return archive_dir / "archive_snapshot.json"


def archive_rows_from_snapshot(campaign_id: str, snapshot: dict[str, list[dict[str, Any]]], *, created_at: str | None = None) -> list[dict[str, Any]]:
    timestamp = created_at or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for bucket_name, entries in snapshot.items():
        for entry in entries:
            rows.append(
                {
                    "campaign_id": campaign_id,
                    "experiment_id": entry["experiment_id"],
                    "reason": f"{bucket_name} metric={entry['metric_value']:.6f}",
                    "rank_bucket": bucket_name,
                    "created_at": timestamp,
                }
            )
    return rows


def _render_archive_markdown(document: dict[str, Any]) -> str:
    lines = [
        f"# Archive Snapshot: {document['campaign_id']}",
        "",
        f"Updated at: {document['updated_at']}",
        "",
    ]
    for bucket_name, entries in document["buckets"].items():
        lines.append(f"## {bucket_name}")
        if not entries:
            lines.append("- empty")
            lines.append("")
            continue
        for entry in entries:
            lines.append(
                "- "
                + f"{entry['experiment_id']} metric={entry['metric_value']:.6f} "
                + f"lane={entry['lane']} complexity={entry['complexity_cost']}"
            )
        lines.append("")
    return "\n".join(lines)


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _run_record_to_dict(record: RunRecord) -> dict[str, Any]:
    return {
        "experiment_id": record.experiment_id,
        "metric_value": record.metric_value,
        "peak_vram_gb": record.peak_vram_gb,
        "complexity_cost": record.complexity_cost,
        "novelty_tags": list(record.novelty_tags),
        "disposition": record.disposition,
        "lane": record.lane,
    }


__all__ = [
    "archive_rows_from_snapshot",
    "archive_snapshot_document",
    "build_archive_snapshot",
    "write_archive_snapshot",
]
