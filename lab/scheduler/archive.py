from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from ..paths import LabPaths
from ..semantics import is_completed_metric_run, is_rankable_experiment
from ..utils import utc_now_iso, write_json
from .novelty import novelty_tags


@dataclass(frozen=True)
class RunRecord:
    experiment_id: str
    metric_value: float
    peak_vram_gb: float
    complexity_cost: int
    novelty_tags: tuple[str, ...]
    disposition: str
    lane: str


def build_archive_snapshot(experiments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    runs: list[RunRecord] = []
    for row in experiments:
        if not is_completed_metric_run(row):
            continue
        if not is_rankable_experiment(row):
            continue
        metric_value = row.get("primary_metric_value")
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


def archive_buckets(
    runs: list[RunRecord],
    *,
    champion_limit: int = 5,
    near_miss_limit: int = 8,
    novel_limit: int = 6,
) -> dict[str, list[RunRecord]]:
    champions = sorted(
        [run for run in runs if run.disposition == "promoted"],
        key=lambda run: (run.metric_value, run.complexity_cost),
    )[:champion_limit]
    pareto = pareto_front(runs)
    near_misses = sorted(
        [run for run in runs if run.disposition == "archived"],
        key=lambda run: (run.metric_value, run.complexity_cost),
    )[:near_miss_limit]

    by_novelty: dict[str, list[RunRecord]] = defaultdict(list)
    for run in runs:
        for tag in run.novelty_tags:
            by_novelty[tag].append(run)

    novel_winners: list[RunRecord] = []
    for _, tagged_runs in sorted(by_novelty.items()):
        best = min(tagged_runs, key=lambda run: (run.metric_value, run.complexity_cost))
        if best not in novel_winners:
            novel_winners.append(best)
    novel_winners = novel_winners[:novel_limit]

    return {
        "champions": champions,
        "pareto": pareto,
        "near_misses": near_misses,
        "novel_winners": novel_winners,
    }


def pareto_front(runs: list[RunRecord]) -> list[RunRecord]:
    front: list[RunRecord] = []
    for candidate in runs:
        dominated = False
        for other in runs:
            if candidate.experiment_id == other.experiment_id:
                continue
            if (
                other.metric_value <= candidate.metric_value
                and other.peak_vram_gb <= candidate.peak_vram_gb
                and (other.metric_value < candidate.metric_value or other.peak_vram_gb < candidate.peak_vram_gb)
            ):
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return sorted(front, key=lambda run: (run.metric_value, run.peak_vram_gb, run.complexity_cost))


__all__ = [
    "archive_rows_from_snapshot",
    "archive_snapshot_document",
    "build_archive_snapshot",
    "write_archive_snapshot",
]
