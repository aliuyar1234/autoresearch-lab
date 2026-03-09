from __future__ import annotations

from pathlib import Path
from typing import Any

from ..ledger.queries import upsert_daily_report
from ..paths import LabPaths, report_root
from ..utils import utc_now_iso, write_json
from .champion import build_champion_cards, render_champion_cards_markdown
from .crashes import build_crash_summary, render_crash_summary_markdown
from .daily import build_daily_report, filter_experiments_for_window, render_daily_report_markdown
from .leaderboard import build_leaderboard, render_leaderboard_markdown


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
        promoted_count=sum(1 for row in window_experiments if str(row.get("disposition")) == "promoted"),
        failed_count=sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
        created_at=generated_at,
    )

    return {
        "ok": True,
        "campaign_id": campaign["campaign_id"],
        "report_date": report_date,
        "report_root": str(root),
        "artifact_paths": artifact_paths,
        "run_count": len(window_experiments),
        "promoted_count": sum(1 for row in window_experiments if str(row.get("disposition")) == "promoted"),
        "failed_count": sum(1 for row in window_experiments if str(row.get("status")) != "completed"),
        "window_started_at": report_payload["header"]["window_started_at"],
        "window_ended_at": report_payload["header"]["window_ended_at"],
        "session_notes": report_payload.get("session_notes", []),
        "recommendations": report_payload["recommendations"]["notes"],
        "latest_champion_experiment_id": leaderboard.get("champion_experiment_id"),
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


__all__ = ["generate_report_bundle"]
