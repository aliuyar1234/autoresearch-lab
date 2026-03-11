from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.campaigns import build_campaign, load_campaign
from lab.campaigns.load import resolve_asset_root
from lab.ledger.db import apply_migrations, connect
from lab.ledger.queries import get_experiment, get_proposal, list_campaign_experiments, list_campaign_proposals, list_daily_reports, list_validation_reviews
from lab.memory import backfill_memory
from lab.paths import build_paths, ensure_managed_roots
from lab.proposals import normalize_proposal_payload
from lab.reports import generate_report_bundle
from lab.runner import execute_experiment
from lab.scheduler import DEFAULT_LANE_MIX, plan_structured_queue
from lab.semantics import is_validated_promotion
from lab.settings import load_settings
from lab.utils import load_schema, read_json, sha256_file, utc_now_iso, validate_payload, write_json


SHOWCASE_ROOT = CURRENT_DIR
DEFAULT_SNAPSHOT_ROOT = SHOWCASE_ROOT / "01_seed_snapshot"
DEFAULT_TARGET_COMMAND = [
    sys.executable,
    "-m",
    "research.dense_gpt.train",
    "--summary-out",
    "{summary_out}",
    "--config-path",
    "{config_path}",
    "--experiment-id",
    "{experiment_id}",
    "--proposal-id",
    "{proposal_id}",
    "--campaign-id",
    "{campaign_id}",
    "--lane",
    "{lane}",
    "--eval-split",
    "{eval_split}",
    "--run-purpose",
    "{run_purpose}",
    "--backend",
    "{backend}",
    "--device-profile",
    "{device_profile}",
    "--repo-root",
    "{repo_root}",
    "--artifacts-root",
    "{artifacts_root}",
    "--cache-root",
    "{cache_root}",
    "--seed",
    "{seed}",
    "--time-budget-seconds",
    "{time_budget_seconds}",
]


def parse_target_command(*, target_command: str | None, target_command_json: str | None) -> list[str]:
    if target_command_json:
        payload = json.loads(target_command_json)
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise ValueError("--target-command-json must decode to a JSON array of strings")
        return payload
    if target_command:
        import shlex

        return shlex.split(target_command, posix=False)
    return list(DEFAULT_TARGET_COMMAND)


def default_output_root(output_root: Path | None) -> Path:
    return (output_root or SHOWCASE_ROOT).resolve()


def workspace_paths(workspace_root: Path):
    settings = load_settings(
        repo_root=REPO_ROOT,
        artifacts_root=workspace_root / "artifacts",
        worktrees_root=workspace_root / ".worktrees",
        db_path=workspace_root / "lab.sqlite3",
        cache_root=workspace_root / "cache",
        env={},
    )
    return build_paths(settings)


def load_showcase_campaign(paths, campaign_id: str) -> dict[str, Any]:
    return load_campaign(paths, campaign_id)


def current_repo_commit() -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def pair_order_for_index(*, index: int, order_mode: str) -> list[str]:
    if order_mode == "remembering-first":
        return ["remembering", "amnesiac"]
    if order_mode == "amnesiac-first":
        return ["amnesiac", "remembering"]
    if order_mode != "alternate":
        raise ValueError(f"unsupported order mode: {order_mode}")
    return ["remembering", "amnesiac"] if index % 2 == 1 else ["amnesiac", "remembering"]


def add_common_command_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--target-command")
    parser.add_argument("--target-command-json")
    parser.add_argument("--device-profile")
    parser.add_argument("--backend")


def prepare_workspace(
    *,
    workspace_root: Path,
    snapshot_root: Path | None,
    campaign_id: str | None = None,
):
    if workspace_root.exists():
        raise FileExistsError(f"workspace root already exists: {workspace_root}")
    paths = workspace_paths(workspace_root)
    ensure_managed_roots(paths)
    if snapshot_root is not None:
        _seed_workspace_from_snapshot(paths, snapshot_root)
    apply_migrations(paths.db_path, paths.sql_root)
    _normalize_transient_proposals(paths.db_path, paths.proposals_root)
    if campaign_id:
        _sync_workspace_campaign_assets(paths, campaign_id)
        if snapshot_root is not None:
            _backfill_legacy_snapshot_memory(paths, campaign_id)
    return paths


def run_showcase_session(
    *,
    paths,
    campaign: dict[str, Any],
    hours: float,
    max_runs: int | None,
    allow_confirm: bool,
    seed_policy: str,
    target_command_template: list[str],
    device_profile: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    apply_migrations(paths.db_path, paths.sql_root)
    session_started_at = utc_now_iso()
    deadline = time.monotonic() + max(0.0, hours) * 3600.0
    executed: list[dict[str, Any]] = []
    queue_refills = 0

    while True:
        if max_runs is not None and len(executed) >= max_runs:
            break
        if hours > 0 and time.monotonic() >= deadline:
            break
        proposal = _next_queued_proposal(paths, str(campaign["campaign_id"]), allow_confirm=allow_confirm)
        if proposal is None:
            refill_count = _fill_queue(paths, campaign, allow_confirm=allow_confirm)
            if refill_count == 0:
                break
            queue_refills += 1
            proposal = _next_queued_proposal(paths, str(campaign["campaign_id"]), allow_confirm=allow_confirm)
            if proposal is None:
                break
        lane = str(proposal["lane"])
        seed = _seed_for_run(campaign, run_index=len(executed), seed_policy=seed_policy)
        time_budget_seconds = int(campaign["budgets"].get(f"{lane}_seconds", campaign["budgets"].get("main_seconds", 300)))
        result = execute_experiment(
            paths=paths,
            proposal=proposal,
            campaign=campaign,
            target_command_template=target_command_template,
            seed=seed,
            time_budget_seconds=time_budget_seconds,
            device_profile=device_profile,
            backend=backend,
        )
        summary = read_json(result.summary_path)
        executed.append(
            {
                "run_index": len(executed) + 1,
                "experiment_id": result.experiment_id,
                "proposal_id": result.proposal_id,
                "status": result.status,
                "crash_class": result.crash_class,
                "proposal_family": summary.get("proposal_family"),
                "proposal_kind": summary.get("proposal_kind"),
                "primary_metric_name": summary.get("primary_metric_name"),
                "primary_metric_value": summary.get("primary_metric_value"),
                "lane": summary.get("lane"),
                "started_at": summary.get("started_at"),
                "ended_at": summary.get("ended_at"),
            }
        )

    with connect(paths.db_path) as connection:
        experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
        report_payload = generate_report_bundle(
            connection,
            paths=paths,
            campaign=campaign,
            experiments=experiments,
            report_date=session_started_at[:10],
            started_at=session_started_at,
            ended_at=utc_now_iso(),
            session_notes=[],
        )
        connection.commit()

    run_curve = build_run_curve(campaign=campaign, executed=executed)
    return {
        "ok": True,
        "campaign_id": campaign["campaign_id"],
        "run_count": len(executed),
        "queue_refills": queue_refills,
        "executed": executed,
        "run_curve": run_curve,
        "report": report_payload,
        "session_started_at": session_started_at,
        "session_ended_at": utc_now_iso(),
    }


def build_run_curve(*, campaign: dict[str, Any], executed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    direction = str(campaign["primary_metric"]["direction"])
    best_metric: float | None = None
    failure_count = 0
    curve: list[dict[str, Any]] = []
    for item in executed:
        metric_value = item.get("primary_metric_value")
        if item.get("status") != "completed":
            failure_count += 1
        if metric_value is not None:
            metric_float = float(metric_value)
            if best_metric is None or _metric_better(metric_float, best_metric, direction=direction):
                best_metric = metric_float
        curve.append(
            {
                "run_index": item["run_index"],
                "experiment_id": item["experiment_id"],
                "status": item["status"],
                "proposal_family": item.get("proposal_family"),
                "primary_metric_value": metric_value,
                "best_metric_so_far": best_metric,
                "failure_count_so_far": failure_count,
            }
        )
    return curve


def summarize_arm_state(
    *,
    paths,
    campaign: dict[str, Any],
    executed_ids: list[str],
    limit: int = 5,
) -> dict[str, Any]:
    with connect(paths.db_path) as connection:
        experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
        reports = list_daily_reports(connection, str(campaign["campaign_id"]), limit=1)
    executed_rows = [row for row in experiments if str(row["experiment_id"]) in set(executed_ids)]
    top_candidates = dedupe_candidates(
        [candidate_record(campaign=campaign, row=row) for row in executed_rows if _has_metric(row)],
        direction=str(campaign["primary_metric"]["direction"]),
        limit=limit,
    )
    failures = [
        candidate_record(campaign=campaign, row=row)
        for row in executed_rows
        if str(row.get("status")) != "completed"
    ][:limit]
    return {
        "campaign_id": campaign["campaign_id"],
        "run_count": len(executed_rows),
        "completed_run_count": sum(1 for row in executed_rows if str(row.get("status")) == "completed"),
        "failed_run_count": sum(1 for row in executed_rows if str(row.get("status")) != "completed"),
        "promoted_count": sum(1 for row in executed_rows if is_validated_promotion(row)),
        "top_candidates": top_candidates,
        "failure_examples": failures,
        "latest_report_path": str(reports[0]["report_json_path"]) if reports else None,
    }


def candidate_record(*, campaign: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    proposal_payload = proposal_payload_from_row(row)
    return {
        "experiment_id": str(row["experiment_id"]),
        "proposal_id": str(row.get("proposal_id") or ""),
        "campaign_id": str(row["campaign_id"]),
        "lane": row.get("lane"),
        "status": row.get("status"),
        "disposition": row.get("disposition"),
        "validation_state": row.get("validation_state"),
        "proposal_family": row.get("proposal_family") or proposal_payload.get("family"),
        "proposal_kind": row.get("proposal_kind") or proposal_payload.get("kind"),
        "primary_metric_name": row.get("primary_metric_name") or campaign["primary_metric"]["name"],
        "primary_metric_value": row.get("primary_metric_value"),
        "idea_signature": row.get("idea_signature") or proposal_payload.get("idea_signature"),
        "parent_ids": proposal_payload.get("parent_ids", []),
        "retrieval_event_id": proposal_payload.get("retrieval_event_id"),
        "evidence_count": len(proposal_payload.get("evidence", [])),
        "evidence_memory_ids": [str(item.get("memory_id")) for item in proposal_payload.get("evidence", []) if str(item.get("memory_id") or "")],
        "anchor_experiment_ids": proposal_payload.get("generation_context", {}).get("anchor_experiment_ids", []),
        "summary_path": row.get("summary_path"),
        "artifact_root": row.get("artifact_root"),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
    }


def proposal_payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        return {}
    payload = json.loads(raw)
    return normalize_proposal_payload(payload) if isinstance(payload, dict) else {}


def dedupe_candidates(
    candidates: list[dict[str, Any]],
    *,
    direction: str,
    limit: int,
) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        metric_value = candidate.get("primary_metric_value")
        if metric_value is None:
            continue
        key = (
            str(candidate.get("proposal_family") or "unknown"),
            str(candidate.get("idea_signature") or candidate.get("experiment_id")),
        )
        existing = best_by_key.get(key)
        if existing is None or _metric_better(float(metric_value), float(existing["primary_metric_value"]), direction=direction):
            best_by_key[key] = candidate
    sorted_candidates = sorted(
        best_by_key.values(),
        key=lambda item: (float(item["primary_metric_value"]), str(item["experiment_id"])),
        reverse=direction == "max",
    )
    return sorted_candidates[:limit]


def select_best_candidate(candidates: list[dict[str, Any]], *, direction: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (float(item["primary_metric_value"]), str(item["experiment_id"])),
        reverse=direction == "max",
    )[0]


def aggregate_compare(*, campaign: dict[str, Any], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    arms = ("remembering", "amnesiac")
    aggregate: dict[str, Any] = {
        "pair_count": len(pairs),
        "wins_by_best_raw_metric": {arm: 0 for arm in arms},
        "mean_best_metric_by_arm": {},
        "mean_repeated_dead_end_rate_by_arm": {},
        "mean_memory_citation_coverage_by_arm": {},
        "mean_promoted_count_by_arm": {},
    }
    direction = str(campaign["primary_metric"]["direction"])
    for pair in pairs:
        best_by_arm: dict[str, float] = {}
        for arm in arms:
            best_candidate = pair["arms"][arm].get("best_candidate")
            if best_candidate and best_candidate.get("primary_metric_value") is not None:
                best_by_arm[arm] = float(best_candidate["primary_metric_value"])
        if len(best_by_arm) == 2:
            winner = "remembering" if _metric_better(best_by_arm["remembering"], best_by_arm["amnesiac"], direction=direction) else "amnesiac"
            aggregate["wins_by_best_raw_metric"][winner] += 1
    for arm in arms:
        aggregate["mean_best_metric_by_arm"][arm] = _mean(
            [
                float(pair["arms"][arm]["best_candidate"]["primary_metric_value"])
                for pair in pairs
                if pair["arms"][arm].get("best_candidate") and pair["arms"][arm]["best_candidate"].get("primary_metric_value") is not None
            ]
        )
        aggregate["mean_repeated_dead_end_rate_by_arm"][arm] = _mean(
            [
                float(pair["arms"][arm]["report"].get("repeated_dead_end_rate"))
                for pair in pairs
                if pair["arms"][arm]["report"].get("repeated_dead_end_rate") is not None
            ]
        )
        aggregate["mean_memory_citation_coverage_by_arm"][arm] = _mean(
            [
                float(pair["arms"][arm]["report"].get("memory_citation_coverage"))
                for pair in pairs
                if pair["arms"][arm]["report"].get("memory_citation_coverage") is not None
            ]
        )
        aggregate["mean_promoted_count_by_arm"][arm] = _mean(
            [float(pair["arms"][arm]["session"]["report"]["promoted_count"]) for pair in pairs]
        )
    return aggregate


def render_compare_markdown(compare_payload: dict[str, Any]) -> str:
    lines = [
        f"# Showcase Compare: {compare_payload['campaign_id']}",
        "",
        f"Repo commit: `{compare_payload['repo_commit']}`",
        f"Pair count: {compare_payload['aggregate']['pair_count']}",
        "",
    ]
    for pair in compare_payload["pairs"]:
        lines.extend(
            [
                f"## {pair['pair_id']}",
                "",
                f"Order: {', '.join(pair['order'])}",
                f"Raw winner: {pair.get('winner_by_best_raw_metric') or 'n/a'}",
            ]
        )
        for arm_name, arm in pair["arms"].items():
            best = arm.get("best_candidate")
            metric_text = "n/a" if not best else f"{float(best['primary_metric_value']):.6f}"
            lines.append(
                f"- {arm_name}: runs={arm['session']['run_count']} promoted={arm['session']['report']['promoted_count']} "
                f"failed={arm['session']['report']['failed_count']} best={metric_text}"
            )
        lines.append("")
    lines.extend(
        [
            "## Aggregate",
            "",
            f"- Raw wins: {json.dumps(compare_payload['aggregate']['wins_by_best_raw_metric'], sort_keys=True)}",
            f"- Mean best metric: {json.dumps(compare_payload['aggregate']['mean_best_metric_by_arm'], sort_keys=True)}",
            f"- Mean repeated-dead-end rate: {json.dumps(compare_payload['aggregate']['mean_repeated_dead_end_rate_by_arm'], sort_keys=True)}",
            f"- Mean memory citation coverage: {json.dumps(compare_payload['aggregate']['mean_memory_citation_coverage_by_arm'], sort_keys=True)}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_replay_payload(
    *,
    paths,
    campaign: dict[str, Any],
    source_experiment_id: str,
    target_command_template: list[str],
    device_profile: str | None,
    backend: str | None,
    eval_split: str,
    run_purpose: str,
    time_budget_seconds: int,
) -> dict[str, Any]:
    with connect(paths.db_path) as connection:
        source_row = get_experiment(connection, source_experiment_id)
        if not source_row:
            raise FileNotFoundError(f"experiment not found: {source_experiment_id}")
        proposal_row = get_proposal(connection, str(source_row.get("proposal_id"))) if source_row.get("proposal_id") else None
    proposal_payload = proposal_payload_from_row({"proposal_json": proposal_row["proposal_json"] if proposal_row else None})
    if not proposal_payload and source_row.get("artifact_root"):
        proposal_payload = read_json(Path(str(source_row["artifact_root"])) / "proposal.json")
    from lab.replay import clone_proposal_for_replay

    replay_proposal = clone_proposal_for_replay(proposal_payload, source_experiment_id=source_experiment_id)
    result = execute_experiment(
        paths=paths,
        proposal=replay_proposal,
        campaign=campaign,
        target_command_template=target_command_template,
        seed=int(source_row.get("seed") or 42),
        time_budget_seconds=time_budget_seconds,
        device_profile=device_profile,
        backend=backend,
        eval_split=eval_split,
        run_purpose=run_purpose,
        replay_source_experiment_id=source_experiment_id,
        score_result=False,
    )
    summary = read_json(result.summary_path)
    return {
        "source_experiment_id": source_experiment_id,
        "replay_experiment_id": result.experiment_id,
        "summary_path": str(result.summary_path),
        "artifact_root": str(result.artifact_root),
        "primary_metric_name": summary.get("primary_metric_name"),
        "primary_metric_value": summary.get("primary_metric_value"),
        "eval_split": eval_split,
        "run_purpose": run_purpose,
    }


def load_snapshot_manifest(snapshot_root: Path) -> dict[str, Any] | None:
    manifest_path = snapshot_root / "MANIFEST.json"
    if not manifest_path.exists():
        return None
    return read_json(manifest_path)


def materialize_snapshot(
    *,
    source_db: Path,
    output_root: Path,
    campaign_ids: list[str],
    include_source_kinds: list[str] | None = None,
    exclude_source_kinds: list[str] | None = None,
    copy_artifacts: bool = True,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot_db_path = output_root / "lab.sqlite3"
    shutil.copy2(source_db, snapshot_db_path)
    included_kinds = _filter_snapshot_db(
        snapshot_db_path=snapshot_db_path,
        campaign_ids=campaign_ids,
        include_source_kinds=include_source_kinds or [],
        exclude_source_kinds=exclude_source_kinds or [],
    )
    artifact_references = build_artifact_references(
        source_db=source_db,
        output_root=output_root,
        campaign_ids=campaign_ids,
        copy_artifacts=copy_artifacts,
    )
    write_json(output_root / "ARTIFACT_REFERENCES.json", artifact_references)
    db_hash = sha256_file(snapshot_db_path)
    copied_hashes = _copied_artifact_hashes(output_root)
    snapshot_hash = _combined_hash(
        {
            "db_sha256": db_hash,
            "copied_hashes": copied_hashes,
            "campaign_ids": campaign_ids,
            "source_kinds": included_kinds,
        }
    )
    counts = snapshot_counts(snapshot_db_path)
    manifest = {
        "source_db_path": str(source_db),
        "snapshot_db_path": str(snapshot_db_path),
        "included_campaign_ids": campaign_ids,
        "included_source_kinds": included_kinds,
        "excluded_sources": sorted(set(exclude_source_kinds or [])),
        "snapshot_timestamp": utc_now_iso(),
        "snapshot_hash": snapshot_hash,
        "db_sha256": db_hash,
        "artifact_reference_path": str(output_root / "ARTIFACT_REFERENCES.json"),
        "counts": counts,
    }
    write_json(output_root / "MANIFEST.json", manifest)
    (output_root / "MANIFEST.md").write_text(render_snapshot_manifest_markdown(manifest, artifact_references), encoding="utf-8")
    return manifest


def build_artifact_references(*, source_db: Path, output_root: Path, campaign_ids: list[str], copy_artifacts: bool) -> dict[str, Any]:
    source_artifacts_root = _infer_artifacts_root(source_db)
    copied: dict[str, list[dict[str, Any]]] = {"archive": [], "reports": [], "proposals": []}
    with sqlite3.connect(source_db) as connection:
        connection.row_factory = sqlite3.Row
        proposal_rows = connection.execute(
            f"SELECT proposal_id, campaign_id FROM proposals WHERE campaign_id IN ({', '.join('?' for _ in campaign_ids)})",
            campaign_ids,
        ).fetchall()
        report_rows = connection.execute(
            f"SELECT campaign_id, report_json_path, report_path FROM daily_reports WHERE campaign_id IN ({', '.join('?' for _ in campaign_ids)})",
            campaign_ids,
        ).fetchall()
    if copy_artifacts:
        for campaign_id in campaign_ids:
            source_archive_root = source_artifacts_root / "archive" / campaign_id
            destination_archive_root = output_root / "archive" / campaign_id
            if source_archive_root.exists():
                shutil.copytree(source_archive_root, destination_archive_root, dirs_exist_ok=True)
                copied["archive"].append(
                    {
                        "campaign_id": campaign_id,
                        "source_path": str(source_archive_root),
                        "copied_path": str(destination_archive_root),
                    }
                )
        for row in report_rows:
            json_path = Path(str(row["report_json_path"]))
            report_root = json_path.parent
            reports_root = source_artifacts_root / "reports"
            if report_root.exists() and reports_root in report_root.parents:
                destination_root = output_root / "reports" / report_root.relative_to(reports_root)
                shutil.copytree(report_root, destination_root, dirs_exist_ok=True)
                copied["reports"].append(
                    {
                        "campaign_id": str(row["campaign_id"]),
                        "source_path": str(report_root),
                        "copied_path": str(destination_root),
                    }
                )
        for row in proposal_rows:
            source_proposal_root = source_artifacts_root / "proposals" / str(row["proposal_id"])
            if source_proposal_root.exists():
                destination_proposal_root = output_root / "proposals" / str(row["proposal_id"])
                shutil.copytree(source_proposal_root, destination_proposal_root, dirs_exist_ok=True)
                copied["proposals"].append(
                    {
                        "campaign_id": str(row["campaign_id"]),
                        "proposal_id": str(row["proposal_id"]),
                        "source_path": str(source_proposal_root),
                        "copied_path": str(destination_proposal_root),
                    }
                )
    return {
        "source_artifacts_root": str(source_artifacts_root),
        "copy_artifacts": copy_artifacts,
        "copied": copied,
    }


def render_snapshot_manifest_markdown(manifest: dict[str, Any], artifact_references: dict[str, Any]) -> str:
    lines = [
        "# Frozen Memory Snapshot",
        "",
        f"- Source DB path: `{manifest['source_db_path']}`",
        f"- Snapshot DB path: `{manifest['snapshot_db_path']}`",
        f"- Source artifacts root: `{artifact_references['source_artifacts_root']}`",
        f"- Included campaign IDs: {', '.join(manifest['included_campaign_ids']) or 'none'}",
        f"- Included source kinds: {', '.join(manifest['included_source_kinds']) or 'none'}",
        f"- Excluded sources: {', '.join(manifest['excluded_sources']) or 'none'}",
        f"- Snapshot timestamp: `{manifest['snapshot_timestamp']}`",
        f"- Snapshot hash: `{manifest['snapshot_hash']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in manifest.get("counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Artifact references", ""])
    for category, entries in artifact_references.get("copied", {}).items():
        lines.append(f"- {category}: {len(entries)} copied roots")
    return "\n".join(lines) + "\n"


def snapshot_counts(snapshot_db_path: Path) -> dict[str, int]:
    with sqlite3.connect(snapshot_db_path) as connection:
        counts: dict[str, int] = {}
        for table in ("experiments", "proposals", "memory_records", "validation_reviews", "daily_reports"):
            try:
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.OperationalError:
                counts[table] = 0
        return counts


def _fill_queue(paths, campaign: dict[str, Any], *, allow_confirm: bool) -> int:
    with connect(paths.db_path) as connection:
        planned = plan_structured_queue(
            connection,
            paths=paths,
            campaign=campaign,
            count=5,
            lane_mix=_night_lane_mix(allow_confirm),
            persist=True,
        )
        return len(planned)


def _next_queued_proposal(paths, campaign_id: str, *, allow_confirm: bool) -> dict[str, Any] | None:
    with connect(paths.db_path) as connection:
        queued = list_campaign_proposals(connection, campaign_id, statuses=["queued"])
    for row in queued:
        if not allow_confirm and str(row.get("lane")) == "confirm":
            continue
        payload = json.loads(row["proposal_json"])
        if isinstance(payload, dict):
            return normalize_proposal_payload(payload)
    return None


def _seed_for_run(campaign: dict[str, Any], *, run_index: int, seed_policy: str) -> int:
    seeds = [int(seed) for seed in campaign["budgets"].get("replication_seeds", [42])]
    if seed_policy == "mixed":
        return seeds[run_index % len(seeds)]
    return seeds[0]


def _night_lane_mix(allow_confirm: bool) -> tuple[tuple[str, int], ...]:
    if allow_confirm:
        return DEFAULT_LANE_MIX
    return tuple((lane, weight) for lane, weight in DEFAULT_LANE_MIX if lane != "confirm")


def _seed_workspace_from_snapshot(paths, snapshot_root: Path) -> None:
    snapshot_root = snapshot_root.resolve()
    source_db = snapshot_root / "lab.sqlite3"
    if not source_db.exists():
        raise FileNotFoundError(f"snapshot database not found: {source_db}")
    shutil.copy2(source_db, paths.db_path)
    for folder_name in ("archive", "reports", "proposals"):
        source_root = snapshot_root / folder_name
        destination_root = paths.artifacts_root / folder_name
        if source_root.exists():
            shutil.copytree(source_root, destination_root, dirs_exist_ok=True)


def _sync_workspace_campaign_assets(paths, campaign_id: str) -> None:
    campaign = load_campaign(paths, campaign_id)
    workspace_asset_root = resolve_asset_root(paths, campaign)
    packed_manifest_path = workspace_asset_root / campaign["assets"]["packed_manifest"]
    if packed_manifest_path.exists():
        return

    canonical_paths = build_paths(load_settings(repo_root=REPO_ROOT, env={}))
    canonical_campaign = load_campaign(canonical_paths, campaign_id)
    canonical_asset_root = resolve_asset_root(canonical_paths, canonical_campaign)
    canonical_packed_manifest_path = canonical_asset_root / canonical_campaign["assets"]["packed_manifest"]
    if not canonical_packed_manifest_path.exists():
        build_campaign(canonical_paths, campaign_id)
    if not canonical_packed_manifest_path.exists():
        raise FileNotFoundError(
            f"canonical campaign assets are missing for showcase workspace sync: {canonical_packed_manifest_path}"
        )

    workspace_asset_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(canonical_asset_root, workspace_asset_root, dirs_exist_ok=True)


def _backfill_legacy_snapshot_memory(paths, campaign_id: str) -> None:
    with connect(paths.db_path) as connection:
        memory_count = int(connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()[0])
        if memory_count > 0:
            return
        campaign = load_campaign(paths, campaign_id)
        experiments = list_campaign_experiments(connection, campaign_id)
        reviews = list_validation_reviews(connection, campaign_id=campaign_id)
        reports = list_daily_reports(connection, campaign_id)
        if not experiments and not reviews and not reports:
            return
        backfill_memory(
            connection,
            paths=paths,
            campaign=campaign,
            experiments=experiments,
            validation_reviews=reviews,
            reports=reports,
        )
        connection.commit()


def _normalize_transient_proposals(db_path: Path, proposals_root: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT proposal_id, proposal_json FROM proposals WHERE status IN ('queued', 'running')"
        ).fetchall()
        for row in rows:
            payload = json.loads(row["proposal_json"]) if row["proposal_json"] else {}
            if isinstance(payload, dict):
                payload["status"] = "superseded"
                proposal_json = json.dumps(payload, sort_keys=True)
            else:
                proposal_json = row["proposal_json"]
            connection.execute(
                "UPDATE proposals SET status = 'superseded', proposal_json = ?, updated_at = datetime('now') WHERE proposal_id = ?",
                (proposal_json, row["proposal_id"]),
            )
            proposal_file = proposals_root / str(row["proposal_id"]) / "proposal.json"
            if proposal_file.exists():
                file_payload = read_json(proposal_file)
                if isinstance(file_payload, dict):
                    file_payload["status"] = "superseded"
                    write_json(proposal_file, file_payload)
        connection.commit()


def _infer_artifacts_root(source_db: Path) -> Path:
    source_db = source_db.resolve()
    db_parent = source_db.parent
    sibling_artifacts_root = db_parent / "artifacts"
    if sibling_artifacts_root.exists():
        return sibling_artifacts_root
    if any((db_parent / child).exists() for child in ("runs", "reports", "archive", "proposals")):
        return db_parent
    return sibling_artifacts_root


def _filter_snapshot_db(
    *,
    snapshot_db_path: Path,
    campaign_ids: list[str],
    include_source_kinds: list[str],
    exclude_source_kinds: list[str],
) -> list[str]:
    allowed_kinds = set(include_source_kinds)
    denied_kinds = set(exclude_source_kinds)
    with sqlite3.connect(snapshot_db_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        placeholders = ", ".join("?" for _ in campaign_ids)
        for table in ("campaigns", "proposals", "experiments", "validation_reviews", "daily_reports", "archive_rows", "retrieval_events"):
            try:
                connection.execute(
                    f"DELETE FROM {table} WHERE campaign_id NOT IN ({placeholders})",
                    campaign_ids,
                )
            except sqlite3.OperationalError:
                continue
        try:
            if not allowed_kinds:
                rows = connection.execute(
                    f"SELECT DISTINCT source_kind FROM memory_records WHERE campaign_id IN ({placeholders})",
                    campaign_ids,
                ).fetchall()
                allowed_kinds = {str(row[0]) for row in rows if row[0]}
            allowed_kinds -= denied_kinds
            if allowed_kinds:
                kind_placeholders = ", ".join("?" for _ in allowed_kinds)
                connection.execute(
                    f"DELETE FROM memory_records WHERE campaign_id IN ({placeholders}) AND source_kind NOT IN ({kind_placeholders})",
                    [*campaign_ids, *sorted(allowed_kinds)],
                )
            else:
                connection.execute(
                    f"DELETE FROM memory_records WHERE campaign_id IN ({placeholders})",
                    campaign_ids,
                )
        except sqlite3.OperationalError:
            allowed_kinds = set()
        for statement in (
            "DELETE FROM artifacts WHERE experiment_id NOT IN (SELECT experiment_id FROM experiments)",
            "DELETE FROM retrieval_event_items WHERE retrieval_event_id NOT IN (SELECT retrieval_event_id FROM retrieval_events)",
            "DELETE FROM retrieval_event_items WHERE memory_id NOT IN (SELECT memory_id FROM memory_records)",
            "DELETE FROM proposal_evidence_links WHERE proposal_id NOT IN (SELECT proposal_id FROM proposals)",
            "DELETE FROM proposal_evidence_links WHERE memory_id NOT IN (SELECT memory_id FROM memory_records)",
            "DELETE FROM proposal_evidence_links WHERE retrieval_event_id IS NOT NULL AND retrieval_event_id NOT IN (SELECT retrieval_event_id FROM retrieval_events)",
        ):
            try:
                connection.execute(statement)
            except sqlite3.OperationalError:
                continue
        connection.commit()
    return sorted(allowed_kinds)


def _copied_artifact_hashes(output_root: Path) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    for relative_root in ("archive", "reports", "proposals"):
        root = output_root / relative_root
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                hashes.append(
                    {
                        "relative_path": str(path.relative_to(output_root)).replace("\\", "/"),
                        "sha256": sha256_file(path),
                    }
                )
    return hashes


def _combined_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _metric_better(candidate: float, baseline: float, *, direction: str) -> bool:
    if direction == "min":
        return candidate < baseline
    if direction == "max":
        return candidate > baseline
    raise ValueError(f"unsupported direction: {direction}")


def _has_metric(row: dict[str, Any]) -> bool:
    return str(row.get("status")) == "completed" and row.get("primary_metric_value") is not None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)
