from __future__ import annotations

from typing import Any

from ..scoring import improvement


def build_leaderboard(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    completed = [row for row in experiments if str(row.get("status")) == "completed" and row.get("primary_metric_value") is not None]
    champion = _best_row(completed, direction=direction, promoted_only=True) or _best_row(completed, direction=direction, promoted_only=False)
    champion_metric = float(champion["primary_metric_value"]) if champion else None

    ranked_rows = sorted(experiments, key=lambda row: _sort_key(row, direction=direction))
    payload_rows = []
    for index, row in enumerate(ranked_rows, start=1):
        metric_value = row.get("primary_metric_value")
        delta_vs_champion = None
        if champion_metric is not None and metric_value is not None and str(row.get("status")) == "completed":
            delta_vs_champion = round(improvement(direction, champion_metric, float(metric_value)), 6)
        payload_rows.append(
            {
                "rank": index,
                "experiment_id": str(row["experiment_id"]),
                "proposal_id": row.get("proposal_id"),
                "proposal_family": row.get("proposal_family"),
                "proposal_kind": row.get("proposal_kind"),
                "lane": row.get("lane"),
                "primary_metric_value": float(metric_value) if metric_value is not None else None,
                "delta_vs_champion": delta_vs_champion,
                "backend": row.get("backend"),
                "peak_vram_gb": float(row.get("peak_vram_gb") or 0.0),
                "complexity_cost": int(row.get("complexity_cost") or 0),
                "status": row.get("status"),
                "disposition": row.get("disposition"),
                "artifact_root": row.get("artifact_root"),
            }
        )

    return {
        "campaign_id": campaign["campaign_id"],
        "primary_metric_name": campaign["primary_metric"]["name"],
        "direction": direction,
        "champion_experiment_id": champion["experiment_id"] if champion else None,
        "rows": payload_rows,
    }


def render_leaderboard_markdown(leaderboard: dict[str, Any]) -> str:
    lines = [
        f"# Leaderboard: {leaderboard['campaign_id']}",
        "",
        f"Primary metric: {leaderboard['primary_metric_name']} ({leaderboard['direction']})",
        f"Champion experiment: {leaderboard['champion_experiment_id'] or 'none'}",
        "",
        "| Rank | Experiment | Family | Kind | Lane | Metric | Delta vs champion | Backend | Peak VRAM | Complexity | Status |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in leaderboard["rows"]:
        metric_text = "-" if row["primary_metric_value"] is None else f"{row['primary_metric_value']:.6f}"
        delta_text = "-" if row["delta_vs_champion"] is None else f"{row['delta_vs_champion']:.6f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    str(row["experiment_id"]),
                    str(row.get("proposal_family") or "-"),
                    str(row.get("proposal_kind") or "-"),
                    str(row.get("lane") or "-"),
                    metric_text,
                    delta_text,
                    str(row.get("backend") or "-"),
                    f"{float(row.get('peak_vram_gb') or 0.0):.3f}",
                    str(int(row.get("complexity_cost") or 0)),
                    str(row.get("status") or "-"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _best_row(experiments: list[dict[str, Any]], *, direction: str, promoted_only: bool) -> dict[str, Any] | None:
    candidates = experiments
    if promoted_only:
        candidates = [row for row in experiments if str(row.get("disposition")) == "promoted"]
    if not candidates:
        return None
    reverse = direction == "max"
    return sorted(
        candidates,
        key=lambda row: (
            float(row["primary_metric_value"]),
            -int(row.get("complexity_cost") or 0) if reverse else int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=reverse,
    )[0]


def _sort_key(row: dict[str, Any], *, direction: str) -> tuple[Any, ...]:
    status = str(row.get("status") or "unknown")
    disposition = str(row.get("disposition") or "")
    status_rank = 0 if status == "completed" else 1
    disposition_rank = {"promoted": 0, "archived": 1, "discarded": 2}.get(disposition, 3)
    metric_value = row.get("primary_metric_value")
    if metric_value is None:
        metric_key = float("inf")
    else:
        metric_key = float(metric_value)
        if direction == "max":
            metric_key = -metric_key
    return (
        status_rank,
        disposition_rank,
        metric_key,
        int(row.get("complexity_cost") or 0),
        str(row.get("experiment_id") or ""),
    )


__all__ = ["build_leaderboard", "render_leaderboard_markdown"]
