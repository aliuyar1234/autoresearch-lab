from __future__ import annotations

from pathlib import Path
from typing import Any

from ..ledger.queries import upsert_daily_report
from ..memory import ingest_report_memory
from ..paths import LabPaths, report_root
from ..utils import utc_now_iso, write_json
from .champion import build_champion_cards, render_champion_cards_markdown
from .crashes import build_crash_summary, render_crash_summary_markdown
from .daily import build_daily_report, filter_experiments_for_window
from .leaderboard import build_leaderboard, render_leaderboard_markdown
from ..semantics import is_validated_promotion


def generate_report_bundle(
    connection,
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    experiments: list[dict[str, Any]],
    report_date: str,
    started_at: str | None = None,
    ended_at: str | None = None,
    session_notes: list[str] | None = None,
) -> dict[str, Any]:
    generated_at = utc_now_iso()
    window_experiments = filter_experiments_for_window(experiments, started_at=started_at, ended_at=ended_at)
    leaderboard = build_leaderboard(campaign, experiments)
    champion_cards = build_champion_cards(campaign, experiments)
    crash_summary = build_crash_summary(window_experiments)

    root = report_root(paths, campaign["campaign_id"], report_date)
    root.mkdir(parents=True, exist_ok=True)
    artifact_paths = {
        "report_md": str(root / "report.md"),
        "report_json": str(root / "report.json"),
        "leaderboard_md": str(root / "leaderboard.md"),
        "leaderboard_json": str(root / "leaderboard.json"),
        "champion_cards_md": str(root / "champion_cards.md"),
        "champion_cards_json": str(root / "champion_cards.json"),
        "crash_summary_md": str(root / "crash_summary.md"),
        "crash_summary_json": str(root / "crash_summary.json"),
    }
    report_payload = build_daily_report(
        campaign=campaign,
        report_date=report_date,
        window_experiments=window_experiments,
        all_experiments=experiments,
        leaderboard=leaderboard,
        champion_cards=champion_cards,
        crash_summary=crash_summary,
        artifact_paths=artifact_paths,
        window_started_at=started_at,
        window_ended_at=ended_at,
        generated_at=generated_at,
        repo_root=str(paths.repo_root),
        session_notes=session_notes,
    )

    write_json(Path(artifact_paths["report_json"]), report_payload)
    Path(artifact_paths["report_md"]).write_text(render_daily_report_markdown(report_payload), encoding="utf-8")
    write_json(Path(artifact_paths["leaderboard_json"]), leaderboard)
    Path(artifact_paths["leaderboard_md"]).write_text(render_leaderboard_markdown(leaderboard), encoding="utf-8")
    write_json(Path(artifact_paths["champion_cards_json"]), champion_cards)
    Path(artifact_paths["champion_cards_md"]).write_text(render_champion_cards_markdown(champion_cards), encoding="utf-8")
    write_json(Path(artifact_paths["crash_summary_json"]), crash_summary)
    Path(artifact_paths["crash_summary_md"]).write_text(render_crash_summary_markdown(crash_summary), encoding="utf-8")
    _write_archive_champion_card(paths, campaign["campaign_id"], champion_cards)

    upsert_daily_report(
        connection,
        campaign_id=str(campaign["campaign_id"]),
        report_date=report_date,
        report_path=artifact_paths["report_md"],
        report_json_path=artifact_paths["report_json"],
        run_count=len(window_experiments),
        promoted_count=sum(1 for row in window_experiments if is_validated_promotion(row)),
        failed_count=sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
        created_at=generated_at,
    )
    ingest_report_memory(
        connection,
        paths=paths,
        campaign=campaign,
        report=report_payload,
        report_json_path=artifact_paths["report_json"],
    )

    return {
        "ok": True,
        "campaign_id": campaign["campaign_id"],
        "report_date": report_date,
        "report_root": str(root),
        "artifact_paths": artifact_paths,
        "run_count": len(window_experiments),
        "promoted_count": sum(1 for row in window_experiments if is_validated_promotion(row)),
        "failed_count": sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
        "window_started_at": report_payload["header"]["window_started_at"],
        "window_ended_at": report_payload["header"]["window_ended_at"],
        "session_notes": report_payload.get("session_notes", []),
        "recommendations": report_payload["recommendations"]["notes"],
        "latest_champion_experiment_id": leaderboard.get("champion_experiment_id"),
        "memory_summary": report_payload.get("memory_summary", {}),
        "repeated_dead_end_rate": report_payload.get("repeated_dead_end_rate"),
        "memory_citation_coverage": report_payload.get("memory_citation_coverage"),
        "negative_citation_coverage": report_payload.get("negative_citation_coverage"),
        "composed_proposal_rate": report_payload.get("composed_proposal_rate"),
        "validation_pass_rate": report_payload.get("validation_pass_rate"),
    }


def _write_archive_champion_card(paths: LabPaths, campaign_id: str, champion_cards: dict[str, Any]) -> None:
    if not champion_cards.get("cards"):
        return
    archive_dir = paths.archive_root / campaign_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    write_json(archive_dir / "champion_card.json", champion_cards["cards"][0])
    (archive_dir / "champion_card.md").write_text(
        render_champion_cards_markdown({"campaign_id": champion_cards["campaign_id"], "cards": champion_cards["cards"][:1]}),
        encoding="utf-8",
    )


def render_daily_report_markdown(report: dict[str, Any]) -> str:
    header = report["header"]
    lines = [
        f"# Morning Report: {report['campaign_id']}",
        "",
        f"Report date: {report['report_date']}",
        f"Window: {header['window_started_at']} -> {header['window_ended_at']}",
        f"Machine / device profile: {header['device_profile'] or 'unknown'}",
    ]
    lines.extend(_render_decision_summary(report))
    lines.extend(_render_top_outcomes(report))
    lines.extend(_render_what_changed(report))
    lines.extend(_render_failure_summary(report))
    lines.extend(_render_archive_updates(report))
    lines.extend(_render_validation_summary(report))
    lines.extend(_render_memory_summary(report))
    lines.extend(_render_recommendations(report))
    lines.extend(_render_session_notes(report))
    lines.extend(_render_appendix(report))
    return "\n".join(lines) + "\n"


def _render_decision_summary(report: dict[str, Any]) -> list[str]:
    champion = report["top_outcomes"]["champion_update"]
    best_confirmed = report["top_outcomes"]["best_confirmed_candidates"]
    best_new = report["top_outcomes"]["best_new_candidates"]
    validation = report["validation_summary"]
    recommendation_notes = list(report["recommendations"].get("notes", []))
    lines = [
        "",
        "## Decision Summary",
        "",
        f"- Current champion: {champion['current_champion_experiment_id'] or 'none yet'}",
        f"- New champion this window: {'yes' if champion['new_champion_emerged'] else 'no'}",
    ]
    if best_confirmed:
        top_confirmed = best_confirmed[0]
        lines.append(
            f"- Highest confirmed result: {top_confirmed['experiment_id']} ({top_confirmed['proposal_family']}) metric={top_confirmed['primary_metric_value']:.6f}"
        )
    elif best_new:
        top_candidate = best_new[0]
        lines.append(
            f"- Highest unconfirmed result: {top_candidate['experiment_id']} ({top_candidate['proposal_family']}) metric={top_candidate['primary_metric_value']:.6f}"
        )
    else:
        lines.append("- Highest result this window: none")
    lines.append(f"- Pending validation backlog: {validation['pending_count']}")
    if recommendation_notes:
        lines.append(f"- Operator focus: {recommendation_notes[0]}")
    return lines


def _render_top_outcomes(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Top Outcomes", ""]
    best_new = report["top_outcomes"]["best_new_candidates"]
    if best_new:
        for item in best_new:
            delta_text = "n/a" if item["delta_vs_previous_champion"] is None else f"{item['delta_vs_previous_champion']:.6f}"
            lines.append(
                f"- Best new candidate: {item['experiment_id']} ({item['proposal_family']}) metric={item['primary_metric_value']:.6f} delta={delta_text}"
            )
    else:
        lines.append("- No completed candidates were recorded in this window.")
    for item in report["top_outcomes"]["best_confirmed_candidates"]:
        lines.append(f"- Best confirmed candidate: {item['experiment_id']} metric={item['primary_metric_value']:.6f}")
    champion = report["top_outcomes"]["champion_update"]
    lines.append(
        f"- New champion emerged: {'yes' if champion['new_champion_emerged'] else 'no'}"
        + (f" ({champion['current_champion_experiment_id']})" if champion["current_champion_experiment_id"] else "")
    )
    if champion["delta_vs_previous_champion"] is not None:
        lines.append(f"- Direct delta vs previous champion: {champion['delta_vs_previous_champion']:.6f}")
    return lines


def _render_what_changed(report: dict[str, Any]) -> list[str]:
    lines = ["", "## What Changed", ""]
    if not report["what_changed"]:
        lines.append("- No proposal-family changes were recorded in this window.")
        return lines
    for family in report["what_changed"]:
        lines.append(
            f"- {family['family']}: {family['run_count']} runs, {family['promoted_count']} promoted, {family['failed_count']} failed; knobs={', '.join(family['top_knobs']) or 'baseline'}"
        )
        if family["worked"]:
            lines.append(f"  worked: {family['worked']}")
        if family["failed"]:
            lines.append(f"  failed: {family['failed']}")
    return lines


def _render_failure_summary(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Failure Summary", ""]
    if not report["failure_summary"]["entries"]:
        lines.append("- No failures in this window.")
        return lines
    for entry in report["failure_summary"]["entries"]:
        lines.append(f"- {entry['crash_class']}: {entry['count']} runs; likely cause: {entry['likely_cause']}")
    return lines


def _render_archive_updates(report: dict[str, Any]) -> list[str]:
    archive = report["archive_updates"]
    return [
        "",
        "## Archive Updates",
        "",
        f"- Newly promoted runs: {', '.join(archive['newly_promoted']) or 'none'}",
        f"- Newly archived near-misses: {', '.join(archive['newly_archived']) or 'none'}",
        f"- Superseded champions: {', '.join(archive['superseded_champions']) or 'none'}",
    ]


def _render_validation_summary(report: dict[str, Any]) -> list[str]:
    validation = report["validation_summary"]
    return [
        "",
        "## Validation",
        "",
        f"- Pending validation: {validation['pending_count']}",
        f"- Confirm passes: {validation['confirm_pass_count']}",
        f"- Confirm fails: {validation['confirm_fail_count']}",
        f"- Audit reviews: {validation['audit_review_count']}",
    ]


def _render_memory_summary(report: dict[str, Any]) -> list[str]:
    memory_summary = report["memory_summary"]
    lines = [
        "",
        "## Memory",
        "",
        f"- Auto-generated proposals: {memory_summary['auto_generated_proposal_count']}",
        f"- Retrieval-backed proposals: {memory_summary['cited_proposal_count']}",
        f"- Negative citations present: {memory_summary['negative_cited_proposal_count']}",
        f"- Retrieval events observed: {memory_summary['retrieval_event_count']}",
        f"- Memory citation coverage: {_ratio_text(report['memory_citation_coverage'])}",
        f"- Negative citation coverage: {_ratio_text(report['negative_citation_coverage'])}",
        f"- Composed proposal rate: {_ratio_text(report['composed_proposal_rate'])}",
        f"- Repeated dead-end rate: {_ratio_text(report['repeated_dead_end_rate'])}",
        f"- Validation pass rate: {_ratio_text(report['validation_pass_rate'])}",
    ]
    for example in memory_summary.get("top_retrieval_examples", [])[:3]:
        lines.append(
            f"- Retrieval example: {example['experiment_id']} cites {example['evidence_count']} memories"
            + (f" ({example['retrieval_event_id']})" if example.get("retrieval_event_id") else "")
        )
    return lines


def _render_recommendations(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Recommendations", ""]
    notes = list(report["recommendations"].get("notes", []))
    if not notes:
        lines.append("- No recommendation notes were generated for this window.")
        return lines
    for note in notes:
        lines.append(f"- {note}")
    return lines


def _render_session_notes(report: dict[str, Any]) -> list[str]:
    notes = list(report.get("session_notes", []))
    if not notes:
        return []
    lines = ["", "## Session Notes", ""]
    for note in notes:
        lines.append(f"- {note}")
    return lines


def _render_appendix(report: dict[str, Any]) -> list[str]:
    lines = ["", "## Appendix", "", "- Artifact paths:"]
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
    return lines


def _ratio_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


__all__ = ["generate_report_bundle", "render_daily_report_markdown"]
