from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from _shared import (
    add_common_command_arguments,
    aggregate_compare,
    current_repo_commit,
    default_output_root,
    DEFAULT_SNAPSHOT_ROOT,
    dedupe_candidates,
    load_showcase_campaign,
    load_snapshot_manifest,
    pair_order_for_index,
    parse_target_command,
    prepare_workspace,
    render_compare_markdown,
    run_showcase_session,
    select_best_candidate,
    summarize_arm_state,
    workspace_paths,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run official remembering vs amnesiac showcase pairs.")
    add_common_command_arguments(parser)
    parser.add_argument("--pairs", type=int, default=2)
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--snapshot-root", type=Path, default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--order", choices=["alternate", "remembering-first", "amnesiac-first"], default="alternate")
    parser.add_argument("--allow-confirm", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-policy", choices=["mixed", "fixed"], default="mixed")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = default_output_root(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    target_command = parse_target_command(
        target_command=args.target_command,
        target_command_json=args.target_command_json,
    )
    probe_paths = workspace_paths(output_root / ".campaign_probe")
    campaign = load_showcase_campaign(probe_paths, str(args.campaign))
    snapshot_manifest = load_snapshot_manifest(args.snapshot_root.resolve())

    pair_summaries: list[dict[str, Any]] = []
    for pair_index in range(1, int(args.pairs) + 1):
        pair_id = f"pair_{pair_index:02d}"
        pair_root = output_root / pair_id
        if pair_root.exists():
            raise FileExistsError(f"pair root already exists: {pair_root}")
        pair_root.mkdir(parents=True, exist_ok=False)
        order = pair_order_for_index(index=pair_index, order_mode=str(args.order))

        workspace_map = {
            "remembering": prepare_workspace(
                workspace_root=pair_root / "remembering",
                snapshot_root=args.snapshot_root.resolve(),
                campaign_id=str(campaign["campaign_id"]),
            ),
            "amnesiac": prepare_workspace(
                workspace_root=pair_root / "amnesiac",
                snapshot_root=None,
                campaign_id=str(campaign["campaign_id"]),
            ),
        }
        arms: dict[str, Any] = {}
        for arm_name in order:
            history_mode = "frozen_snapshot" if arm_name == "remembering" else "empty_history"
            arms[arm_name] = _run_arm_session(
                arm_name=arm_name,
                arm_root=pair_root / arm_name,
                paths=workspace_map[arm_name],
                campaign=campaign,
                target_command=target_command,
                hours=float(args.hours),
                max_runs=args.max_runs,
                allow_confirm=bool(args.allow_confirm),
                seed_policy=str(args.seed_policy),
                device_profile=getattr(args, "device_profile", None),
                backend=getattr(args, "backend", None),
                history_mode=history_mode,
                snapshot_manifest=snapshot_manifest if arm_name == "remembering" else None,
            )

        best_candidates = {arm_name: arm.get("best_candidate") for arm_name, arm in arms.items()}
        winner = _winner_by_best_metric(best_candidates, direction=str(campaign["primary_metric"]["direction"]))
        pair_summary = {
            "pair_id": pair_id,
            "order": order,
            "winner_by_best_raw_metric": winner,
            "arms": arms,
        }
        write_json(pair_root / "pair_summary.json", pair_summary)
        pair_summaries.append(pair_summary)

    candidate_summary = _build_candidate_summary(campaign=campaign, pairs=pair_summaries)
    write_json(output_root / "candidate_summary.json", candidate_summary)

    compare_payload = {
        "campaign_id": campaign["campaign_id"],
        "repo_commit": current_repo_commit(),
        "snapshot_manifest_path": str(args.snapshot_root.resolve() / "MANIFEST.json") if snapshot_manifest is not None else None,
        "pairs": pair_summaries,
        "aggregate": aggregate_compare(campaign=campaign, pairs=pair_summaries),
        "candidate_summary_path": str(output_root / "candidate_summary.json"),
    }
    write_json(output_root / "compare.json", compare_payload)
    (output_root / "compare.md").write_text(render_compare_markdown(compare_payload), encoding="utf-8")
    print(json.dumps(compare_payload, indent=2, sort_keys=True))
    return 0


def _run_arm_session(
    *,
    arm_name: str,
    arm_root: Path,
    paths,
    campaign: dict[str, Any],
    target_command: list[str],
    hours: float,
    max_runs: int | None,
    allow_confirm: bool,
    seed_policy: str,
    device_profile: str | None,
    backend: str | None,
    history_mode: str,
    snapshot_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    session = run_showcase_session(
        paths=paths,
        campaign=campaign,
        hours=hours,
        max_runs=max_runs,
        allow_confirm=allow_confirm,
        seed_policy=seed_policy,
        target_command_template=target_command,
        device_profile=device_profile,
        backend=backend,
    )
    executed_ids = [str(item["experiment_id"]) for item in session["executed"]]
    candidate_summary = summarize_arm_state(paths=paths, campaign=campaign, executed_ids=executed_ids)
    candidate_summary_path = arm_root / "candidate_summary.json"
    write_json(candidate_summary_path, candidate_summary)

    report_payload = session["report"]
    report_paths = dict(report_payload.get("artifact_paths", {}))
    leaderboard_snapshot_path = arm_root / "leaderboard_snapshot.json"
    archive_snapshot_path = arm_root / "archive_snapshot.json"
    _copy_if_exists(Path(str(report_paths.get("leaderboard_json") or "")), leaderboard_snapshot_path)
    _copy_if_exists(paths.archive_root / str(campaign["campaign_id"]) / "archive_snapshot.json", archive_snapshot_path)

    arm_manifest = {
        "arm": arm_name,
        "history_mode": history_mode,
        "snapshot_manifest": snapshot_manifest,
        "workspace_root": str(arm_root),
        "db_path": str(paths.db_path),
        "artifacts_root": str(paths.artifacts_root),
        "cache_root": str(paths.cache_root),
        "worktrees_root": str(paths.worktrees_root),
        "target_command": target_command,
        "session": session,
        "candidate_summary_path": str(candidate_summary_path),
        "leaderboard_snapshot_path": str(leaderboard_snapshot_path) if leaderboard_snapshot_path.exists() else None,
        "archive_snapshot_path": str(archive_snapshot_path) if archive_snapshot_path.exists() else None,
        "report_paths": report_paths,
    }
    run_manifest_path = arm_root / "run_manifest.json"
    write_json(run_manifest_path, arm_manifest)
    best_candidate = select_best_candidate(
        list(candidate_summary.get("top_candidates", [])),
        direction=str(campaign["primary_metric"]["direction"]),
    )
    return {
        "arm": arm_name,
        "history_mode": history_mode,
        "workspace_root": str(arm_root),
        "db_path": str(paths.db_path),
        "artifacts_root": str(paths.artifacts_root),
        "run_manifest_path": str(run_manifest_path),
        "candidate_summary_path": str(candidate_summary_path),
        "leaderboard_snapshot_path": str(leaderboard_snapshot_path) if leaderboard_snapshot_path.exists() else None,
        "archive_snapshot_path": str(archive_snapshot_path) if archive_snapshot_path.exists() else None,
        "report": report_payload,
        "report_paths": report_paths,
        "session": session,
        "best_candidate": best_candidate,
    }


def _build_candidate_summary(*, campaign: dict[str, Any], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = {"remembering": [], "amnesiac": []}
    for pair in pairs:
        for arm_name in ("remembering", "amnesiac"):
            by_arm[arm_name].extend(pair["arms"][arm_name]["session"]["executed"])
    return {
        "campaign_id": campaign["campaign_id"],
        "pairs": [pair["pair_id"] for pair in pairs],
        "top_candidates_by_arm": {
            arm_name: dedupe_candidates(
                [
                    {
                        **pair["arms"][arm_name]["best_candidate"],
                        "pair_id": pair["pair_id"],
                    }
                    for pair in pairs
                    if pair["arms"][arm_name].get("best_candidate")
                ],
                direction=str(campaign["primary_metric"]["direction"]),
                limit=10,
            )
            for arm_name in ("remembering", "amnesiac")
        },
    }


def _winner_by_best_metric(best_candidates: dict[str, Any], *, direction: str) -> str | None:
    remembering = best_candidates.get("remembering")
    amnesiac = best_candidates.get("amnesiac")
    if not remembering or not amnesiac:
        return None
    if float(remembering["primary_metric_value"]) == float(amnesiac["primary_metric_value"]):
        return "tie"
    return "remembering" if (
        (direction == "min" and float(remembering["primary_metric_value"]) < float(amnesiac["primary_metric_value"]))
        or (direction == "max" and float(remembering["primary_metric_value"]) > float(amnesiac["primary_metric_value"]))
    ) else "amnesiac"


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists() or not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
