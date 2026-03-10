from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reference_impl.report_recommendations import build_recommendations

from ..paths import resolve_managed_path
from ..proposals import normalize_proposal_payload
from ..scheduler.archive import build_archive_snapshot
from ..scheduler.compose import flatten_override_paths
from ..scheduler.exhaustion import exhaustion_summary
from ..scoring import improvement
from ..semantics import is_completed_metric_run, is_pending_validation, is_rankable_experiment, is_validated_promotion
from ..utils import read_json


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
    repo_root: str,
    session_notes: list[str] | None = None,
) -> dict[str, Any]:
    header = _build_header(campaign, window_experiments, window_started_at=window_started_at, window_ended_at=window_ended_at)
    top_outcomes = _build_top_outcomes(campaign, window_experiments, all_experiments, leaderboard)
    what_changed = _build_what_changed(window_experiments)
    archive_updates = _build_archive_updates(window_experiments, all_experiments)
    validation_summary = _build_validation_summary(window_experiments)
    memory_summary = _build_memory_summary(window_experiments)
    scheduler_metrics = _build_scheduler_metrics(window_experiments, all_experiments)
    recommendations = _build_recommendation_section(window_experiments)
    appendix = _build_appendix(
        campaign=campaign,
        window_experiments=window_experiments,
        artifact_paths=artifact_paths,
        generated_at=generated_at,
        report_date=report_date,
        repo_root=repo_root,
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
        "validation_summary": validation_summary,
        "memory_summary": memory_summary,
        "repeated_dead_end_rate": scheduler_metrics["repeated_dead_end_rate"],
        "memory_citation_coverage": scheduler_metrics["memory_citation_coverage"],
        "negative_citation_coverage": scheduler_metrics["negative_citation_coverage"],
        "composed_proposal_rate": scheduler_metrics["composed_proposal_rate"],
        "validation_pass_rate": scheduler_metrics["validation_pass_rate"],
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

    lines.extend(["", "## Validation", ""])
    validation = report["validation_summary"]
    lines.append(f"- Pending validation: {validation['pending_count']}")
    lines.append(f"- Confirm passes: {validation['confirm_pass_count']}")
    lines.append(f"- Confirm fails: {validation['confirm_fail_count']}")
    lines.append(f"- Audit reviews: {validation['audit_review_count']}")

    lines.extend(["", "## Memory", ""])
    memory_summary = report["memory_summary"]
    lines.append(f"- Auto-generated proposals: {memory_summary['auto_generated_proposal_count']}")
    lines.append(f"- Retrieval-backed proposals: {memory_summary['cited_proposal_count']}")
    lines.append(f"- Negative citations present: {memory_summary['negative_cited_proposal_count']}")
    lines.append(f"- Retrieval events observed: {memory_summary['retrieval_event_count']}")
    lines.append(f"- Memory citation coverage: {_ratio_text(report['memory_citation_coverage'])}")
    lines.append(f"- Negative citation coverage: {_ratio_text(report['negative_citation_coverage'])}")
    lines.append(f"- Composed proposal rate: {_ratio_text(report['composed_proposal_rate'])}")
    lines.append(f"- Repeated dead-end rate: {_ratio_text(report['repeated_dead_end_rate'])}")
    lines.append(f"- Validation pass rate: {_ratio_text(report['validation_pass_rate'])}")
    for example in memory_summary.get("top_retrieval_examples", [])[:3]:
        lines.append(
            f"- Retrieval example: {example['experiment_id']} cites {example['evidence_count']} memories"
            + (f" ({example['retrieval_event_id']})" if example.get("retrieval_event_id") else "")
        )

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
        runtime_effective = row.get("runtime_effective") or {}
        runtime_text = "runtime=n/a"
        if isinstance(runtime_effective, dict) and runtime_effective:
            runtime_text = (
                f"runtime=db{runtime_effective.get('device_batch_size')} "
                f"eval{runtime_effective.get('eval_batch_size')} "
                f"compile={runtime_effective.get('compile_enabled')}"
            )
        headroom = row.get("vram_headroom_gb")
        headroom_text = "headroom=n/a" if headroom is None else f"headroom={float(headroom):.3f}GB"
        autotune_hit = row.get("autotune_cache_hit")
        autotune_text = "autotune=n/a" if autotune_hit is None else f"autotune={'hit' if autotune_hit else 'miss'}"
        lines.append(
            f"  - {row['experiment_id']} family={row['proposal_family']} lane={row['lane']} status={row['status']} metric={metric_text} "
            f"backend={row.get('backend')} {runtime_text} {headroom_text} {autotune_text}"
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
        "total_promoted_runs": sum(1 for row in window_experiments if is_validated_promotion(row)),
        "total_failed_runs": sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
    }


def _build_top_outcomes(
    campaign: dict[str, Any],
    window_experiments: list[dict[str, Any]],
    all_experiments: list[dict[str, Any]],
    leaderboard: dict[str, Any],
) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    completed_window = [row for row in window_experiments if is_completed_metric_run(row) and is_rankable_experiment(row)]
    best_new = _top_metric_rows(completed_window, direction=direction, limit=3)
    best_confirmed = _top_metric_rows([row for row in completed_window if is_validated_promotion(row)], direction=direction, limit=3)
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
            if is_completed_metric_run(row) and str(row.get("disposition")) in {"promoted", "archived", "pending_validation"}:
                worked.append(str(row["experiment_id"]))
            if str(row.get("status")) != "completed":
                failed.append(f"{row['experiment_id']} ({row.get('crash_class') or 'unknown'})")
        summaries.append(
            {
                "family": family,
                "run_count": len(rows),
                "promoted_count": sum(1 for row in rows if is_validated_promotion(row)),
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
    promoted = [row["experiment_id"] for row in window_experiments if is_validated_promotion(row)]
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
        if disposition in {"promoted", "archived", "pending_validation"}:
            helpful_tags.extend(tags)
        else:
            harmful_tags.extend(tags)
        if disposition == "archived":
            near_miss_count += 1
        if is_validated_promotion(row):
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
    campaign: dict[str, Any],
    window_experiments: list[dict[str, Any]],
    *,
    artifact_paths: dict[str, str],
    generated_at: str,
    report_date: str,
    repo_root: str,
) -> dict[str, Any]:
    run_table = [
        _appendix_row(campaign, row, repo_root=repo_root)
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
        if is_validated_promotion(row)
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
        "new_champion_emerged": str(current_champion["experiment_id"]) in window_ids and is_validated_promotion(current_champion),
        "current_champion_experiment_id": str(current_champion["experiment_id"]),
        "previous_champion_experiment_id": str(previous_row["experiment_id"]) if previous_row else None,
        "previous_champion_metric": float(previous_row["primary_metric_value"]) if previous_row else None,
        "delta_vs_previous_champion": delta,
    }


def _appendix_row(campaign: dict[str, Any], row: dict[str, Any], *, repo_root: str) -> dict[str, Any]:
    runtime = _load_runtime_appendix_payload(row, repo_root=repo_root)
    peak_vram_gb = float(row.get("peak_vram_gb") or 0.0)
    max_peak_vram_gb = float(campaign["runtime"].get("max_peak_vram_gb", 0.0) or 0.0)
    return {
        "experiment_id": str(row["experiment_id"]),
        "proposal_id": row.get("proposal_id"),
        "proposal_family": row.get("proposal_family") or _proposal_payload(row).get("family"),
        "proposal_kind": row.get("proposal_kind") or _proposal_payload(row).get("kind"),
        "lane": row.get("lane"),
        "eval_split": row.get("eval_split"),
        "run_purpose": row.get("run_purpose"),
        "status": row.get("status"),
        "disposition": row.get("disposition"),
        "validation_state": row.get("validation_state"),
        "validation_review_id": row.get("validation_review_id"),
        "primary_metric_value": float(row["primary_metric_value"]) if row.get("primary_metric_value") is not None else None,
        "artifact_root": row.get("artifact_root"),
        "backend": row.get("backend"),
        "device_profile": row.get("device_profile"),
        "peak_vram_gb": peak_vram_gb,
        "vram_headroom_gb": round(max_peak_vram_gb - peak_vram_gb, 6) if max_peak_vram_gb > 0 else None,
        "autotune_cache_hit": runtime.get("autotune", {}).get("from_cache") if isinstance(runtime.get("autotune"), dict) else None,
        "runtime_defaults": runtime.get("runtime_defaults"),
        "runtime_overlay": runtime.get("runtime_overlay"),
        "runtime_effective": runtime.get("runtime_effective"),
        "autotune": runtime.get("autotune"),
    }


def _load_runtime_appendix_payload(row: dict[str, Any], *, repo_root: str) -> dict[str, Any]:
    artifact_root = row.get("artifact_root")
    if not artifact_root:
        return {}
    root = resolve_managed_path(_AppendixPaths(repo_root=Path(repo_root).resolve()), str(artifact_root))
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = read_json(manifest_path)
    return {
        "runtime_defaults": manifest.get("runtime_defaults"),
        "runtime_overlay": manifest.get("runtime_overlay"),
        "runtime_effective": manifest.get("runtime_effective"),
        "autotune": manifest.get("autotune"),
    }


class _AppendixPaths:
    def __init__(self, *, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.artifacts_root = repo_root / "artifacts"
        self.worktrees_root = repo_root / ".worktrees"


def _build_validation_summary(window_experiments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pending_count": sum(1 for row in window_experiments if is_pending_validation(row)),
        "pending_experiment_ids": [str(row["experiment_id"]) for row in window_experiments if is_pending_validation(row)],
        "confirm_pass_count": sum(
            1
            for row in window_experiments
            if str(row.get("lane")) == "confirm" and is_validated_promotion(row)
        ),
        "confirm_fail_count": sum(
            1
            for row in window_experiments
            if str(row.get("lane")) == "confirm" and str(row.get("validation_state")) == "failed"
        ),
        "audit_review_count": sum(1 for row in window_experiments if str(row.get("run_purpose")) == "audit"),
    }


def _build_memory_summary(window_experiments: list[dict[str, Any]]) -> dict[str, Any]:
    auto_generated = [row for row in window_experiments if _is_auto_generated(row)]
    cited = [row for row in auto_generated if _proposal_payload(row).get("evidence")]
    negative_cited = [
        row
        for row in auto_generated
        if any(str(item.get("role") or "") == "warning" for item in _proposal_payload(row).get("evidence", []))
    ]
    top_examples = sorted(
        [
            {
                "experiment_id": str(row["experiment_id"]),
                "proposal_id": row.get("proposal_id"),
                "retrieval_event_id": _proposal_payload(row).get("retrieval_event_id"),
                "evidence_count": len(_proposal_payload(row).get("evidence", [])),
                "roles": sorted({str(item.get("role") or "") for item in _proposal_payload(row).get("evidence", [])}),
                "memory_ids": [str(item.get("memory_id") or "") for item in _proposal_payload(row).get("evidence", [])[:4]],
            }
            for row in cited
        ],
        key=lambda item: (-int(item["evidence_count"]), str(item["experiment_id"])),
    )[:5]
    return {
        "auto_generated_proposal_count": len(auto_generated),
        "cited_proposal_count": len(cited),
        "negative_cited_proposal_count": len(negative_cited),
        "retrieval_event_count": sum(1 for row in auto_generated if _proposal_payload(row).get("retrieval_event_id")),
        "top_retrieval_examples": top_examples,
    }


def _build_scheduler_metrics(window_experiments: list[dict[str, Any]], all_experiments: list[dict[str, Any]]) -> dict[str, float | None]:
    auto_generated = [row for row in window_experiments if _is_auto_generated(row)]
    dead_end_denominator = [row for row in auto_generated if str(_proposal_payload(row).get("family") or "") != "ablation"]
    repeated_dead_end_count = sum(1 for row in dead_end_denominator if _proposal_was_pre_exhausted(row, all_experiments))
    memory_cited_count = sum(1 for row in auto_generated if _proposal_payload(row).get("evidence"))
    negative_cited_count = sum(
        1
        for row in auto_generated
        if any(str(item.get("role") or "") == "warning" for item in _proposal_payload(row).get("evidence", []))
    )
    composed_count = sum(
        1
        for row in auto_generated
        if str(_proposal_payload(row).get("family") or "") == "combine"
        or len(_proposal_payload(row).get("source_experiments") or []) >= 2
    )
    validation_pass_denominator = sum(
        1
        for row in window_experiments
        if str(row.get("lane") or "") == "confirm" and str(row.get("validation_state") or "") in {"passed", "failed"}
    )
    validation_pass_count = sum(
        1
        for row in window_experiments
        if str(row.get("lane") or "") == "confirm" and str(row.get("validation_state") or "") == "passed"
    )
    return {
        "repeated_dead_end_rate": _safe_ratio(repeated_dead_end_count, len(dead_end_denominator)),
        "memory_citation_coverage": _safe_ratio(memory_cited_count, len(auto_generated)),
        "negative_citation_coverage": _safe_ratio(negative_cited_count, len(auto_generated)),
        "composed_proposal_rate": _safe_ratio(composed_count, len(auto_generated)),
        "validation_pass_rate": _safe_ratio(validation_pass_count, validation_pass_denominator),
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
    return normalize_proposal_payload(payload) if isinstance(payload, dict) else {}


def _event_datetime(row: dict[str, Any]) -> datetime | None:
    return parse_iso_timestamp(str(row.get("ended_at") or row.get("started_at") or ""))


def _proposal_created_datetime(row: dict[str, Any]) -> datetime | None:
    return parse_iso_timestamp(str(_proposal_payload(row).get("created_at") or row.get("started_at") or ""))


def _proposal_was_pre_exhausted(row: dict[str, Any], all_experiments: list[dict[str, Any]]) -> bool:
    proposal = _proposal_payload(row)
    signature = str(proposal.get("idea_signature") or row.get("idea_signature") or "")
    if not signature:
        return False
    created_dt = _proposal_created_datetime(row)
    prior = [
        item
        for item in all_experiments
        if str(item.get("campaign_id") or "") == str(row.get("campaign_id") or "")
        and str(item.get("experiment_id") or "") != str(row.get("experiment_id") or "")
        and (created_dt is None or (_proposal_created_datetime(item) is not None and _proposal_created_datetime(item) < created_dt))
    ]
    stats = exhaustion_summary(prior, campaign_id=str(row.get("campaign_id") or "")).get(signature)
    return bool(stats and stats.get("exhausted"))


def _is_auto_generated(row: dict[str, Any]) -> bool:
    return str(_proposal_payload(row).get("generator") or "") == "scheduler"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _ratio_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


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
