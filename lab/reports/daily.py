from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from reference_impl.report_recommendations import build_recommendations

from ..scheduler.archive import build_archive_snapshot
from ..scheduler.compose import flatten_override_paths
from ..scoring import improvement


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def filter_experiments_for_window(
    experiments: list[dict[str, Any]],
    *,
    started_at: str | None,
    ended_at: str | None,
) -> list[dict[str, Any]]:
    start_dt = parse_iso_timestamp(started_at)
    end_dt = parse_iso_timestamp(ended_at)
    if start_dt is None and end_dt is None:
        return list(experiments)

    filtered: list[dict[str, Any]] = []
    for row in experiments:
        event_dt = _event_datetime(row)
        if event_dt is None:
            continue
        if start_dt is not None and event_dt < start_dt:
            continue
        if end_dt is not None and event_dt > end_dt:
            continue
        filtered.append(row)
    return filtered


def build_daily_report(
    *,
    campaign: dict[str, Any],
    report_date: str,
    window_experiments: list[dict[str, Any]],
    all_experiments: list[dict[str, Any]],
    leaderboard: dict[str, Any],
    champion_cards: dict[str, Any],
    crash_summary: dict[str, Any],
    artifact_paths: dict[str, str],
    window_started_at: str | None,
    window_ended_at: str | None,
    generated_at: str,
    session_notes: list[str] | None = None,
) -> dict[str, Any]:
    header = _build_header(campaign, window_experiments, window_started_at=window_started_at, window_ended_at=window_ended_at)
    top_outcomes = _build_top_outcomes(campaign, window_experiments, all_experiments, leaderboard)
    what_changed = _build_what_changed(window_experiments)
    archive_updates = _build_archive_updates(window_experiments, all_experiments)
    recommendations = _build_recommendation_section(window_experiments)
    appendix = _build_appendix(
        window_experiments,
        artifact_paths=artifact_paths,
        generated_at=generated_at,
        report_date=report_date,
    )
    return {
        "report_type": "daily",
        "campaign_id": campaign["campaign_id"],
        "report_date": report_date,
        "generated_at": generated_at,
        "header": header,
        "top_outcomes": top_outcomes,
        "what_changed": what_changed,
        "failure_summary": crash_summary,
        "archive_updates": archive_updates,
        "recommendations": recommendations,
        "session_notes": list(session_notes or []),
        "appendix": appendix,
        "leaderboard_preview": leaderboard["rows"][:10],
        "champion_cards_preview": champion_cards["cards"][:3],
    }


def render_daily_report_markdown(report: dict[str, Any]) -> str:
    header = report["header"]
    lines = [
        f"# Morning Report: {report['campaign_id']}",
        "",
        f"Report date: {report['report_date']}",
        f"Window: {header['window_started_at']} -> {header['window_ended_at']}",
        f"Machine / device profile: {header['device_profile'] or 'unknown'}",
        "",
        "## Header",
        "",
        f"- Total runs attempted: {header['total_runs_attempted']}",
        f"- Total successful runs: {header['total_successful_runs']}",
        f"- Total promoted runs: {header['total_promoted_runs']}",
        f"- Total failed runs: {header['total_failed_runs']}",
        "",
        "## Top Outcomes",
        "",
    ]
    if report["top_outcomes"]["best_new_candidates"]:
        for item in report["top_outcomes"]["best_new_candidates"]:
            delta_text = "n/a" if item["delta_vs_previous_champion"] is None else f"{item['delta_vs_previous_champion']:.6f}"
            lines.append(
                f"- Best new candidate: {item['experiment_id']} ({item['proposal_family']}) metric={item['primary_metric_value']:.6f} delta={delta_text}"
            )
    else:
        lines.append("- No completed candidates were recorded in this window.")
    if report["top_outcomes"]["best_confirmed_candidates"]:
        for item in report["top_outcomes"]["best_confirmed_candidates"]:
            lines.append(f"- Best confirmed candidate: {item['experiment_id']} metric={item['primary_metric_value']:.6f}")
    champion = report["top_outcomes"]["champion_update"]
    lines.append(
        f"- New champion emerged: {'yes' if champion['new_champion_emerged'] else 'no'}"
        + (f" ({champion['current_champion_experiment_id']})" if champion["current_champion_experiment_id"] else "")
    )
    if champion["delta_vs_previous_champion"] is not None:
        lines.append(f"- Direct delta vs previous champion: {champion['delta_vs_previous_champion']:.6f}")

    lines.extend(["", "## What Changed", ""])
    if report["what_changed"]:
        for family in report["what_changed"]:
            lines.append(
                f"- {family['family']}: {family['run_count']} runs, {family['promoted_count']} promoted, {family['failed_count']} failed; knobs={', '.join(family['top_knobs']) or 'baseline'}"
            )
            if family["worked"]:
                lines.append(f"  worked: {family['worked']}")
            if family["failed"]:
                lines.append(f"  failed: {family['failed']}")
    else:
        lines.append("- No proposal-family changes were recorded in this window.")

    lines.extend(["", "## Failure Summary", ""])
    if report["failure_summary"]["entries"]:
        for entry in report["failure_summary"]["entries"]:
            lines.append(f"- {entry['crash_class']}: {entry['count']} runs; likely cause: {entry['likely_cause']}")
    else:
        lines.append("- No failures in this window.")

    lines.extend(["", "## Archive Updates", ""])
    archive = report["archive_updates"]
    lines.append(f"- Newly promoted runs: {', '.join(archive['newly_promoted']) or 'none'}")
    lines.append(f"- Newly archived near-misses: {', '.join(archive['newly_archived']) or 'none'}")
    lines.append(f"- Superseded champions: {', '.join(archive['superseded_champions']) or 'none'}")

    lines.extend(["", "## Recommendations", ""])
    for note in report["recommendations"]["notes"]:
        lines.append(f"- {note}")

    if report.get("session_notes"):
        lines.extend(["", "## Session Notes", ""])
        for note in report["session_notes"]:
            lines.append(f"- {note}")

    lines.extend(["", "## Appendix", ""])
    lines.append("- Artifact paths:")
    for name, path in report["appendix"]["artifact_paths"].items():
        lines.append(f"  - {name}: {path}")
    lines.append("- Run table:")
    for row in report["appendix"]["run_table"]:
        metric_text = "n/a" if row["primary_metric_value"] is None else f"{row['primary_metric_value']:.6f}"
        lines.append(
            f"  - {row['experiment_id']} family={row['proposal_family']} lane={row['lane']} status={row['status']} metric={metric_text}"
        )
    lines.append("")
    lines.append(f"Generated at: {report['appendix']['generation_metadata']['generated_at']}")
    return "\n".join(lines) + "\n"


def _build_header(
    campaign: dict[str, Any],
    window_experiments: list[dict[str, Any]],
    *,
    window_started_at: str | None,
    window_ended_at: str | None,
) -> dict[str, Any]:
    timestamps = [row.get("started_at") for row in window_experiments if row.get("started_at")] + [
        row.get("ended_at") for row in window_experiments if row.get("ended_at")
    ]
    timestamps = [str(item) for item in timestamps if item]
    return {
        "campaign": campaign["campaign_id"],
        "window_started_at": window_started_at or (min(timestamps) if timestamps else datetime.now(timezone.utc).isoformat()),
        "window_ended_at": window_ended_at or (max(timestamps) if timestamps else datetime.now(timezone.utc).isoformat()),
        "device_profile": _most_common([row.get("device_profile") for row in window_experiments]),
        "total_runs_attempted": len(window_experiments),
        "total_successful_runs": sum(1 for row in window_experiments if str(row.get("status")) == "completed"),
        "total_promoted_runs": sum(
            1 for row in window_experiments if str(row.get("status")) == "completed" and str(row.get("disposition")) == "promoted"
        ),
        "total_failed_runs": sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
    }


def _build_top_outcomes(
    campaign: dict[str, Any],
    window_experiments: list[dict[str, Any]],
    all_experiments: list[dict[str, Any]],
    leaderboard: dict[str, Any],
) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    completed_window = [row for row in window_experiments if str(row.get("status")) == "completed" and row.get("primary_metric_value") is not None]
    best_new = _top_metric_rows(completed_window, direction=direction, limit=3)
    best_confirmed = _top_metric_rows([row for row in completed_window if str(row.get("lane")) == "confirm"], direction=direction, limit=3)
    champion_update = _champion_update(campaign, window_experiments, all_experiments, leaderboard)
    return {
        "best_new_candidates": [_outcome_row(campaign, row, champion_update.get("previous_champion_metric")) for row in best_new],
        "best_confirmed_candidates": [_outcome_row(campaign, row, champion_update.get("previous_champion_metric")) for row in best_confirmed],
        "champion_update": champion_update,
    }


def _build_what_changed(window_experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in window_experiments:
        family = str(row.get("proposal_family") or _proposal_payload(row).get("family") or "manual")
        by_family[family].append(row)

    summaries: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        knob_counter: Counter[str] = Counter()
        worked: list[str] = []
        failed: list[str] = []
        for row in rows:
            proposal_payload = _proposal_payload(row)
            for path, _ in flatten_override_paths(proposal_payload.get("config_overrides", {})):
                knob_counter[path] += 1
            if str(row.get("status")) == "completed" and str(row.get("disposition")) in {"promoted", "archived"}:
                worked.append(str(row["experiment_id"]))
            if str(row.get("status")) != "completed":
                failed.append(f"{row['experiment_id']} ({row.get('crash_class') or 'unknown'})")
        summaries.append(
            {
                "family": family,
                "run_count": len(rows),
                "promoted_count": sum(1 for row in rows if str(row.get("disposition")) == "promoted"),
                "failed_count": sum(1 for row in rows if str(row.get("status")) != "completed"),
                "top_knobs": [path for path, _ in knob_counter.most_common(5)],
                "worked": ", ".join(worked[:3]) if worked else "",
                "failed": ", ".join(failed[:3]) if failed else "",
            }
        )
    return summaries


def _build_archive_updates(window_experiments: list[dict[str, Any]], all_experiments: list[dict[str, Any]]) -> dict[str, Any]:
    window_snapshot = build_archive_snapshot(window_experiments)
    full_snapshot = build_archive_snapshot(all_experiments)
    promoted = [row["experiment_id"] for row in window_experiments if str(row.get("disposition")) == "promoted"]
    archived = [row["experiment_id"] for row in window_experiments if str(row.get("disposition")) == "archived"]
    full_champions = [entry["experiment_id"] for entry in full_snapshot.get("champions", [])]
    window_champions = [entry["experiment_id"] for entry in window_snapshot.get("champions", [])]
    superseded = [experiment_id for experiment_id in full_champions if experiment_id not in window_champions][:5]
    return {
        "newly_promoted": promoted,
        "newly_archived": archived,
        "superseded_champions": superseded,
    }


def _build_recommendation_section(window_experiments: list[dict[str, Any]]) -> dict[str, Any]:
    helpful_tags: list[str] = []
    harmful_tags: list[str] = []
    recent_crash_classes: list[str] = []
    near_miss_count = 0
    confirm_promotions = 0

    for row in window_experiments:
        proposal_payload = _proposal_payload(row)
        tags = [path for path, _ in flatten_override_paths(proposal_payload.get("config_overrides", {}))]
        if str(row.get("status")) != "completed":
            recent_crash_classes.append(str(row.get("crash_class") or "unknown"))
            harmful_tags.extend(tags)
            continue
        disposition = str(row.get("disposition") or "")
        if disposition in {"promoted", "archived"}:
            helpful_tags.extend(tags)
        else:
            harmful_tags.extend(tags)
        if disposition == "archived":
            near_miss_count += 1
        if disposition == "promoted" and str(row.get("lane")) == "confirm":
            confirm_promotions += 1

    notes = build_recommendations(
        recent_crash_classes=recent_crash_classes,
        repeated_helpful_tags=helpful_tags,
        repeated_harmful_tags=harmful_tags,
        near_miss_count=near_miss_count,
        confirm_promotions=confirm_promotions,
    )
    return {"notes": notes}


def _build_appendix(
    window_experiments: list[dict[str, Any]],
    *,
    artifact_paths: dict[str, str],
    generated_at: str,
    report_date: str,
) -> dict[str, Any]:
    run_table = [
        {
            "experiment_id": str(row["experiment_id"]),
            "proposal_id": row.get("proposal_id"),
            "proposal_family": row.get("proposal_family") or _proposal_payload(row).get("family"),
            "proposal_kind": row.get("proposal_kind") or _proposal_payload(row).get("kind"),
            "lane": row.get("lane"),
            "status": row.get("status"),
            "disposition": row.get("disposition"),
            "primary_metric_value": float(row["primary_metric_value"]) if row.get("primary_metric_value") is not None else None,
            "artifact_root": row.get("artifact_root"),
        }
        for row in sorted(window_experiments, key=lambda item: str(item.get("started_at") or ""), reverse=True)
    ]
    return {
        "run_table": run_table,
        "artifact_paths": artifact_paths,
        "generation_metadata": {
            "generated_at": generated_at,
            "report_date": report_date,
            "included_run_count": len(window_experiments),
        },
    }


def _champion_update(
    campaign: dict[str, Any],
    window_experiments: list[dict[str, Any]],
    all_experiments: list[dict[str, Any]],
    leaderboard: dict[str, Any],
) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    current_champion_id = leaderboard.get("champion_experiment_id")
    current_champion = next((row for row in all_experiments if str(row["experiment_id"]) == str(current_champion_id)), None)
    if current_champion is None:
        return {
            "new_champion_emerged": False,
            "current_champion_experiment_id": None,
            "previous_champion_experiment_id": None,
            "previous_champion_metric": None,
            "delta_vs_previous_champion": None,
        }

    current_dt = _event_datetime(current_champion)
    prior_candidates = [
        row
        for row in all_experiments
        if str(row.get("status")) == "completed"
        and str(row.get("disposition")) == "promoted"
        and row.get("primary_metric_value") is not None
        and str(row["experiment_id"]) != str(current_champion["experiment_id"])
        and (current_dt is None or (_event_datetime(row) is not None and _event_datetime(row) < current_dt))
    ]
    previous = _top_metric_rows(prior_candidates, direction=direction, limit=1)
    previous_row = previous[0] if previous else None
    delta = None
    if previous_row is not None:
        delta = round(improvement(direction, float(previous_row["primary_metric_value"]), float(current_champion["primary_metric_value"])), 6)
    window_ids = {str(row["experiment_id"]) for row in window_experiments}
    return {
        "new_champion_emerged": str(current_champion["experiment_id"]) in window_ids and str(current_champion.get("disposition")) == "promoted",
        "current_champion_experiment_id": str(current_champion["experiment_id"]),
        "previous_champion_experiment_id": str(previous_row["experiment_id"]) if previous_row else None,
        "previous_champion_metric": float(previous_row["primary_metric_value"]) if previous_row else None,
        "delta_vs_previous_champion": delta,
    }


def _outcome_row(campaign: dict[str, Any], row: dict[str, Any], previous_champion_metric: float | None) -> dict[str, Any]:
    metric_value = float(row["primary_metric_value"])
    delta = None
    if previous_champion_metric is not None:
        delta = round(improvement(str(campaign["primary_metric"]["direction"]), previous_champion_metric, metric_value), 6)
    return {
        "experiment_id": str(row["experiment_id"]),
        "proposal_id": row.get("proposal_id"),
        "proposal_family": row.get("proposal_family") or _proposal_payload(row).get("family"),
        "primary_metric_value": metric_value,
        "delta_vs_previous_champion": delta,
    }


def _top_metric_rows(experiments: list[dict[str, Any]], *, direction: str, limit: int) -> list[dict[str, Any]]:
    reverse = direction == "max"
    return sorted(
        experiments,
        key=lambda row: (
            float(row["primary_metric_value"]),
            int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=reverse,
    )[:limit]


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _event_datetime(row: dict[str, Any]) -> datetime | None:
    return parse_iso_timestamp(str(row.get("ended_at") or row.get("started_at") or ""))


def _most_common(values: list[Any]) -> Any:
    counter = Counter(item for item in values if item)
    if not counter:
        return None
    return counter.most_common(1)[0][0]


__all__ = [
    "build_daily_report",
    "filter_experiments_for_window",
    "parse_iso_timestamp",
    "render_daily_report_markdown",
]
