from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from research.dense_gpt.search_space import resolve_dense_config

from .campaigns import build_campaign, list_campaigns, load_campaign, verify_campaign
from .cleanup import run_cleanup
from .code_proposals import CodeProposalExportError, CodeProposalImportError, code_proposal_ready, export_code_proposal_pack, import_code_proposal_result
from .doctor import run_doctor
from .ledger.db import apply_migrations, connect, list_schema_versions
from .ledger.queries import (
    get_experiment,
    get_latest_daily_report,
    get_proposal,
    list_archive_rows,
    list_campaign_experiments,
    list_campaign_proposals,
    list_prior_experiments,
    upsert_campaign,
    upsert_proposal,
)
from .night import run_night_session
from .paths import build_paths, ensure_managed_roots, missing_repo_markers, stringify_paths
from .preflight import run_preflight
from .reports import generate_report_bundle
from .replay import load_replay_proposal
from .runner import execute_experiment
from .scheduler import (
    DEFAULT_LANE_MIX,
    SchedulerGenerationError,
    archive_snapshot_document,
    build_archive_snapshot,
    generate_structured_proposal,
    plan_structured_queue,
)
from .scoring import best_baseline, explain_experiment_score
from .settings import LabSettings, SettingsError, load_settings
from .smoke_assets import SmokeAssetError, ensure_smoke_campaign_assets
from .utils import load_schema, read_json, utc_now_iso, validate_payload

EXIT_SUCCESS = 0
EXIT_USER_ERROR = 2
EXIT_PREFLIGHT_FAILURE = 3
EXIT_RUN_FAILURE = 4
EXIT_SCHEMA_FAILURE = 5
EXIT_INTERRUPTED = 6
GENERATABLE_FAMILIES = ("baseline", "exploit", "ablation", "combine", "novel")


def _build_common_parser(*, suppress_defaults: bool = False) -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS if suppress_defaults else None)
    common.add_argument("--repo-root", type=Path)
    common.add_argument("--artifacts-root", type=Path)
    common.add_argument("--db-path", type=Path)
    common.add_argument("--worktrees-root", type=Path)
    common.add_argument("--cache-root", type=Path)
    common.add_argument("--json", action="store_true")
    common.add_argument("--verbose", action="store_true")
    return common


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _lab_env_template(settings: LabSettings) -> str:
    return "\n".join(
        [
            "# Local overrides for Autoresearch Lab.",
            "# Relative paths resolve from the repo root.",
            f"# LAB_ARTIFACTS_ROOT={_relative_or_absolute(settings.artifacts_root, settings.repo_root)}",
            f"# LAB_WORKTREES_ROOT={_relative_or_absolute(settings.worktrees_root, settings.repo_root)}",
            f"# LAB_DB_PATH={_relative_or_absolute(settings.db_path, settings.repo_root)}",
            f"# LAB_CACHE_ROOT={_relative_or_absolute(settings.cache_root, settings.repo_root)}",
            "",
        ]
    )


def _load_settings_from_args(args: argparse.Namespace) -> LabSettings:
    return load_settings(
        repo_root=getattr(args, "repo_root", None),
        artifacts_root=getattr(args, "artifacts_root", None),
        worktrees_root=getattr(args, "worktrees_root", None),
        db_path=getattr(args, "db_path", None),
        cache_root=getattr(args, "cache_root", None),
    )


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    missing = missing_repo_markers(paths.repo_root)
    if missing:
        raise SettingsError(f"repo root is missing required lab files: {', '.join(missing)}")

    created_roots = ensure_managed_roots(paths)
    db_created = apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    schema_versions = list_schema_versions(paths.db_path)

    env_created = False
    if not paths.env_file.exists():
        paths.env_file.write_text(_lab_env_template(settings), encoding="utf-8")
        env_created = True

    payload = {
        "ok": True,
        "repo_root": str(paths.repo_root),
        "created_roots": stringify_paths(created_roots),
        "db_path": str(paths.db_path),
        "db_created": db_created,
        "schema_versions": schema_versions,
        "env_file": str(paths.env_file),
        "env_file_created": env_created,
        "verified_paths": [
            str(paths.docs_root),
            str(paths.schemas_root),
            str(paths.sql_root),
        ],
    }
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_preflight(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    result = run_preflight(
        paths,
        campaign_id=getattr(args, "campaign", None),
        benchmark_backends=bool(getattr(args, "benchmark_backends", False)),
    )
    _emit(result.to_dict(), args.json)
    return EXIT_SUCCESS if result.ok else EXIT_PREFLIGHT_FAILURE


def _cmd_smoke(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    smoke_campaign_id = getattr(args, "campaign", None) or "base_2k"
    if args.gpu:
        try:
            ensure_smoke_campaign_assets(paths, smoke_campaign_id)
        except SmokeAssetError as exc:
            raise SettingsError(str(exc)) from exc
    result = run_preflight(paths, campaign_id=smoke_campaign_id, benchmark_backends=bool(args.gpu))

    schema_files = sorted(str(path.relative_to(paths.repo_root)) for path in paths.schemas_root.glob("*.json"))
    smoke_ok = all(result.import_checks.values()) and result.artifact_root_writable and paths.db_path.exists() and bool(schema_files)
    tiny_gpu = None

    if args.gpu:
        smoke_ok = smoke_ok and result.device is not None and bool(result.backend_candidates)
        if result.device is None:
            result.warnings.append("gpu smoke requested but no CUDA device was detected")
        elif smoke_ok:
            tiny_gpu = _run_tiny_gpu_smoke(paths, smoke_campaign_id, result)
            smoke_ok = smoke_ok and bool(tiny_gpu.get("ok"))
            if not tiny_gpu.get("ok"):
                result.warnings.append(str(tiny_gpu.get("error") or "tiny gpu smoke failed"))

    payload = result.to_dict()
    payload.update(
        {
            "ok": smoke_ok,
            "db_exists": paths.db_path.exists(),
            "schema_files": schema_files,
            "gpu_mode": args.gpu,
            "tiny_gpu_run": tiny_gpu,
        }
    )
    _emit(payload, args.json)
    return EXIT_SUCCESS if smoke_ok else EXIT_PREFLIGHT_FAILURE


def _cmd_unimplemented(args: argparse.Namespace) -> int:
    payload = {
        "ok": False,
        "command": getattr(args, "command_name", args.command),
        "status": "not_implemented",
        "message": f"{getattr(args, 'command_name', args.command)} is not implemented in Phase 0",
    }
    _emit(payload, getattr(args, "json", False))
    return EXIT_USER_ERROR


def _cmd_campaign_list(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = {
        "ok": True,
        "campaigns": list_campaigns(paths),
    }
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_campaign_show(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign show requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = load_campaign(paths, args.campaign)
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_campaign_build(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign build requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = build_campaign(paths, args.campaign, source_dir=getattr(args, "source_dir", None))
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_campaign_verify(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign verify requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = verify_campaign(paths, args.campaign)
    _emit(payload, args.json)
    return EXIT_SUCCESS if payload["ok"] else EXIT_PREFLIGHT_FAILURE


def _cmd_campaign_queue(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign queue requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    campaign = _load_campaign(paths, args.campaign)
    connection = connect(paths.db_path)
    try:
        timestamp = utc_now_iso()
        upsert_campaign(connection, campaign, timestamp=timestamp)
        queue = plan_structured_queue(
            connection,
            paths=paths,
            campaign=campaign,
            count=int(getattr(args, "count", 5)),
            lane=getattr(args, "lane", None),
            family=getattr(args, "family", None),
            persist=bool(getattr(args, "apply", False)),
        )
        if getattr(args, "apply", False):
            for proposal in queue:
                validate_payload(proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
                upsert_proposal(connection, proposal, updated_at=proposal["created_at"])
            connection.commit()
    finally:
        connection.close()

    payload = {
        "ok": True,
        "campaign_id": args.campaign,
        "apply": bool(getattr(args, "apply", False)),
        "count": len(queue),
        "lane_mix": [{"lane": lane_name, "weight": weight} for lane_name, weight in DEFAULT_LANE_MIX],
        "proposals": [
            {
                "proposal_id": proposal["proposal_id"],
                "lane": proposal["lane"],
                "family": proposal["family"],
                "kind": proposal["kind"],
                "config_fingerprint": proposal.get("config_fingerprint"),
                "parent_ids": proposal["parent_ids"],
            }
            for proposal in queue
        ],
    }
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _parse_target_command(args: argparse.Namespace) -> list[str]:
    if getattr(args, "target_command_json", None):
        command = json.loads(args.target_command_json)
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise SettingsError("--target-command-json must decode to a JSON array of strings")
        return command
    if getattr(args, "target_command", None):
        return shlex.split(args.target_command, posix=False)
    return [
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


def _load_campaign(paths, campaign_id: str) -> dict[str, object]:
    manifest_path = paths.campaigns_root / campaign_id / "campaign.json"
    if not manifest_path.exists():
        raise SettingsError(f"campaign manifest not found: {manifest_path}")
    payload = read_json(manifest_path)
    validate_payload(payload, load_schema(paths.schemas_root / "campaign.schema.json"))
    return payload


def _load_proposal_from_args(args: argparse.Namespace, paths) -> dict[str, object]:
    provided_sources = [
        bool(getattr(args, "proposal", None)),
        bool(getattr(args, "proposal_id", None)),
        bool(getattr(args, "generate", None)),
    ]
    if sum(provided_sources) != 1:
        raise SettingsError("run requires exactly one of --proposal, --proposal-id, or --generate")
    if getattr(args, "generate", None):
        if getattr(args, "generate", None) != "structured":
            raise SettingsError(f"unsupported generator mode: {args.generate}")
        if not getattr(args, "campaign", None):
            raise SettingsError("run --generate structured requires --campaign")
        if not getattr(args, "lane", None):
            raise SettingsError("run --generate structured requires --lane")
        campaign = _load_campaign(paths, str(args.campaign))
        connection = connect(paths.db_path)
        try:
            payload = generate_structured_proposal(
                connection,
                paths=paths,
                campaign=campaign,
                lane=str(args.lane),
                family=getattr(args, "family", None),
            )
        except SchedulerGenerationError as exc:
            raise SettingsError(str(exc)) from exc
        finally:
            connection.close()
        validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
        return payload
    if getattr(args, "proposal", None):
        payload = read_json(Path(args.proposal))
        validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
        return payload
    if getattr(args, "proposal_id", None):
        connection = connect(paths.db_path)
        try:
            row = get_proposal(connection, args.proposal_id)
        finally:
            connection.close()
        if not row:
            raise SettingsError(f"proposal not found: {args.proposal_id}")
        payload = json.loads(row["proposal_json"])
        validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
        return payload
    raise SettingsError("run requires --proposal or --proposal-id")


def _time_budget_for_lane(campaign: dict[str, object], lane: str) -> int:
    budgets = campaign["budgets"]
    key = f"{lane}_seconds"
    return int(budgets[key])


def _cmd_run(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")

    proposal = _load_proposal_from_args(args, paths)
    if proposal.get("kind") == "code_patch" and not code_proposal_ready(proposal):
        raise SettingsError("code_patch proposal is not ready to run; import a returned patch or worktree first")
    campaign = _load_campaign(paths, str(proposal["campaign_id"]))
    seed = int(getattr(args, "seed", None) or campaign["budgets"].get("replication_seeds", [42])[0])
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(proposal["lane"])))
    result = execute_experiment(
        paths=paths,
        proposal=proposal,
        campaign=campaign,
        target_command_template=_parse_target_command(args),
        seed=seed,
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
    )

    payload = {
        "ok": result.status == "completed" and not result.schema_failed,
        "experiment_id": result.experiment_id,
        "proposal_id": result.proposal_id,
        "proposal_family": proposal["family"],
        "proposal_kind": proposal["kind"],
        "status": result.status,
        "crash_class": result.crash_class,
        "artifact_root": str(result.artifact_root),
        "summary_path": str(result.summary_path),
        "primary_metric_value": result.primary_metric_value,
        "schema_failed": result.schema_failed,
    }
    _emit(payload, args.json)
    if result.schema_failed:
        return EXIT_SCHEMA_FAILURE
    return EXIT_SUCCESS if result.status == "completed" else EXIT_RUN_FAILURE


def _cmd_replay(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")

    proposal, replay_source_experiment_id = load_replay_proposal(
        paths,
        experiment_id=getattr(args, "experiment", None),
        proposal_id=getattr(args, "proposal", None),
    )
    campaign = _load_campaign(paths, str(proposal["campaign_id"]))
    seed = int(getattr(args, "seed", None) or campaign["budgets"].get("replication_seeds", [42])[0])
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(proposal["lane"])))

    result = execute_experiment(
        paths=paths,
        proposal=proposal,
        campaign=campaign,
        target_command_template=_parse_target_command(args),
        seed=seed,
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
        replay_source_experiment_id=replay_source_experiment_id,
    )

    payload = {
        "ok": result.status == "completed" and not result.schema_failed,
        "experiment_id": result.experiment_id,
        "proposal_id": result.proposal_id,
        "status": result.status,
        "artifact_root": str(result.artifact_root),
        "summary_path": str(result.summary_path),
        "source_experiment_id": replay_source_experiment_id,
    }
    _emit(payload, args.json)
    if result.schema_failed:
        return EXIT_SCHEMA_FAILURE
    return EXIT_SUCCESS if result.status == "completed" else EXIT_RUN_FAILURE


def _cmd_export_code_proposal(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    connection = connect(paths.db_path)
    try:
        row = get_proposal(connection, args.proposal_id)
        if not row:
            raise SettingsError(f"proposal not found: {args.proposal_id}")
        proposal = json.loads(row["proposal_json"])
        campaign = _load_campaign(paths, proposal["campaign_id"])
        experiments = list_campaign_experiments(connection, proposal["campaign_id"])
        best_comparator = _best_comparator(campaign, experiments)
        parent_experiments = [item for item in experiments if item["experiment_id"] in proposal.get("parent_ids", [])]
    finally:
        connection.close()

    try:
        payload = export_code_proposal_pack(
            paths=paths,
            campaign=campaign,
            proposal=proposal,
            best_comparator=best_comparator,
            parent_experiments=parent_experiments,
        )
    except CodeProposalExportError as exc:
        raise SettingsError(str(exc)) from exc
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_import_code_proposal(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    connection = connect(paths.db_path)
    try:
        row = get_proposal(connection, args.proposal_id)
        if not row:
            raise SettingsError(f"proposal not found: {args.proposal_id}")
        proposal = json.loads(row["proposal_json"])
        try:
            updated_proposal, payload = import_code_proposal_result(
                paths=paths,
                proposal=proposal,
                patch_path=getattr(args, "patch_path", None),
                worktree_path=getattr(args, "worktree_path", None),
            )
        except CodeProposalImportError as exc:
            raise SettingsError(str(exc)) from exc
        validate_payload(updated_proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
        upsert_proposal(connection, updated_proposal, updated_at=utc_now_iso())
        connection.commit()
    finally:
        connection.close()
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_report(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("report requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    campaign = _load_campaign(paths, args.campaign)
    report_date = str(getattr(args, "date", None) or utc_now_iso()[:10])
    connection = connect(paths.db_path)
    try:
        experiments = list_campaign_experiments(connection, args.campaign)
        payload = generate_report_bundle(
            connection,
            paths=paths,
            campaign=campaign,
            experiments=experiments,
            report_date=report_date,
            started_at=getattr(args, "from_timestamp", None),
            ended_at=getattr(args, "to_timestamp", None),
        )
        connection.commit()
    finally:
        connection.close()
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_cleanup(args: argparse.Namespace) -> int:
    if bool(getattr(args, "apply", False)) and bool(getattr(args, "dry_run", False)):
        raise SettingsError("cleanup accepts either --apply or --dry-run, not both")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    connection = connect(paths.db_path)
    try:
        payload = run_cleanup(
            connection,
            paths=paths,
            apply=bool(getattr(args, "apply", False)),
            campaign_id=getattr(args, "campaign", None),
        )
        if getattr(args, "apply", False):
            connection.commit()
    finally:
        connection.close()
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_doctor(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = run_doctor(paths, campaign_id=getattr(args, "campaign", None))
    _emit(payload, args.json)
    return EXIT_SUCCESS if payload.get("ok") else EXIT_PREFLIGHT_FAILURE


def _cmd_night(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("night requires --campaign")
    if float(getattr(args, "hours", 8.0)) <= 0 and getattr(args, "max_runs", None) is None:
        raise SettingsError("night requires positive --hours or --max-runs")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    campaign = _load_campaign(paths, args.campaign)
    payload = run_night_session(
        paths=paths,
        campaign=campaign,
        hours=float(getattr(args, "hours", 8.0)),
        max_runs=getattr(args, "max_runs", None),
        allow_confirm=bool(getattr(args, "allow_confirm", False)),
        seed_policy=str(getattr(args, "seed_policy", "fixed")),
        target_command_template=_parse_target_command(args),
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
    )
    _emit(payload, args.json)
    if payload.get("status") == "interrupted":
        return EXIT_INTERRUPTED
    return EXIT_SUCCESS if payload.get("ok") else EXIT_PREFLIGHT_FAILURE


def _cmd_inspect(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    connection = connect(paths.db_path)
    try:
        if args.experiment:
            row = get_experiment(connection, args.experiment)
            if not row:
                raise SettingsError(f"experiment not found: {args.experiment}")
            payload = {
                "kind": "experiment",
                "experiment_id": row["experiment_id"],
                "proposal_id": row["proposal_id"],
                "campaign_id": row["campaign_id"],
                "lane": row["lane"],
                "status": row["status"],
                "disposition": row["disposition"],
                "crash_class": row["crash_class"],
                "proposal_family": row["proposal_family"],
                "proposal_kind": row["proposal_kind"],
                "primary_metric_name": row["primary_metric_name"],
                "primary_metric_value": row["primary_metric_value"],
                "artifact_root": row["artifact_root"],
                "summary_path": row["summary_path"],
            }
        elif args.proposal:
            row = get_proposal(connection, args.proposal)
            if not row:
                raise SettingsError(f"proposal not found: {args.proposal}")
            proposal_payload = json.loads(row["proposal_json"])
            payload = {
                "kind": "proposal",
                "proposal_id": row["proposal_id"],
                "campaign_id": row["campaign_id"],
                "lane": row["lane"],
                "status": row["status"],
                "family": row["family"],
                "kind_value": row["kind"],
                "generator": row["generator"],
                "complexity_cost": row["complexity_cost"],
                "config_fingerprint": proposal_payload.get("config_fingerprint"),
                "code_patch_imported": bool(isinstance(proposal_payload.get("code_patch"), dict) and proposal_payload["code_patch"].get("import_root")),
                "code_patch_patch_path": proposal_payload.get("code_patch", {}).get("patch_path")
                if isinstance(proposal_payload.get("code_patch"), dict)
                else None,
            }
        elif args.campaign:
            campaign = _load_campaign(paths, args.campaign)
            experiments = list_campaign_experiments(connection, args.campaign)
            queued_proposals = list_campaign_proposals(connection, args.campaign, statuses=["queued"])
            latest_report = get_latest_daily_report(connection, args.campaign)
            archive_path = paths.archive_root / args.campaign / "archive_snapshot.json"
            archive_document = (
                read_json(archive_path)
                if archive_path.exists()
                else archive_snapshot_document(
                    campaign_id=args.campaign,
                    snapshot=build_archive_snapshot(experiments),
                )
            )
            payload = {
                "kind": "campaign",
                "campaign_id": campaign["campaign_id"],
                "title": campaign["title"],
                "active": campaign["active"],
                "primary_metric_name": campaign["primary_metric"]["name"],
                "archive_path": str(archive_path),
                "archive_row_count": len(list_archive_rows(connection, args.campaign)),
                "archive_buckets": {
                    bucket_name: [item["experiment_id"] for item in entries]
                    for bucket_name, entries in archive_document["buckets"].items()
                },
                "experiment_count": len(experiments),
                "queued_proposal_count": len(queued_proposals),
                "queued_proposals": [row["proposal_id"] for row in queued_proposals[:10]],
                "latest_report": latest_report,
            }
            if latest_report and latest_report.get("report_json_path") and Path(str(latest_report["report_json_path"])).exists():
                report_payload = read_json(Path(str(latest_report["report_json_path"])))
                payload["latest_report_preview"] = {
                    "recommendations": report_payload.get("recommendations", {}).get("notes", []),
                    "session_notes": report_payload.get("session_notes", []),
                    "artifact_paths": report_payload.get("appendix", {}).get("artifact_paths", {}),
                    "leaderboard_preview": report_payload.get("leaderboard_preview", []),
                    "champion_cards_preview": report_payload.get("champion_cards_preview", []),
                }
        else:
            raise SettingsError("inspect requires --experiment, --proposal, or --campaign")
    finally:
        connection.close()
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _cmd_score(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root / "001_ledger.sql")
    connection = connect(paths.db_path)
    try:
        row = get_experiment(connection, args.experiment)
        if not row:
            raise SettingsError(f"experiment not found: {args.experiment}")
        campaign = _load_campaign(paths, row["campaign_id"])
        prior_experiments = list_prior_experiments(
            connection,
            row["campaign_id"],
            row["lane"],
            exclude_experiment_id=row["experiment_id"],
        )
    finally:
        connection.close()

    baseline = best_baseline(prior_experiments, direction=str(campaign["primary_metric"]["direction"]))
    explanation = explain_experiment_score(experiment=row, campaign=campaign, baseline=baseline)
    payload = {
        "experiment_id": row["experiment_id"],
        "status": row["status"],
        "crash_class": row["crash_class"],
        "primary_metric_name": row["primary_metric_name"],
        "primary_metric_value": row["primary_metric_value"],
        **explanation.to_dict(),
    }
    _emit(payload, args.json)
    return EXIT_SUCCESS


def _best_comparator(campaign: dict[str, object], experiments: list[dict[str, object]]) -> dict[str, object] | None:
    completed = [row for row in experiments if row.get("status") == "completed" and row.get("primary_metric_value") is not None]
    if not completed:
        return None
    reverse = str(campaign["primary_metric"]["direction"]) == "max"
    return sorted(
        completed,
        key=lambda row: (
            float(row["primary_metric_value"]),
            int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=reverse,
    )[0]


def _run_tiny_gpu_smoke(paths, campaign_id: str, result) -> dict[str, object]:
    campaign = _load_campaign(paths, campaign_id)
    smoke_root = paths.artifacts_root / "smoke"
    config_path = smoke_root / "tiny_gpu_config.json"
    summary_path = smoke_root / "tiny_gpu_summary.json"
    config = resolve_dense_config(campaign, {})
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    backend = "sdpa"
    if result.backend_selection and isinstance(result.backend_selection, dict):
        backend = str(result.backend_selection.get("backend", backend))
    elif result.backend_candidates:
        backend = str(result.backend_candidates[0])

    command = [
        sys.executable,
        "-m",
        "research.dense_gpt.train",
        "--summary-out",
        str(summary_path),
        "--config-path",
        str(config_path),
        "--experiment-id",
        "smoke_gpu_exp",
        "--proposal-id",
        "smoke_gpu_proposal",
        "--campaign-id",
        campaign_id,
        "--lane",
        "scout",
        "--backend",
        backend,
        "--device-profile",
        str(result.device_profile or "generic_single_gpu_nvidia"),
        "--repo-root",
        str(paths.repo_root),
        "--artifacts-root",
        str(paths.artifacts_root),
        "--cache-root",
        str(paths.cache_root),
        "--seed",
        "42",
        "--time-budget-seconds",
        "8",
        "--max-steps",
        "3",
        "--eval-batches",
        "1",
        "--tiny",
        "--require-cuda",
    ]
    completed = subprocess.run(
        command,
        cwd=paths.repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, object] = {
        "ok": completed.returncode == 0 and summary_path.exists(),
        "command": command,
        "summary_path": str(summary_path),
        "returncode": completed.returncode,
    }
    if summary_path.exists():
        payload["summary"] = read_json(summary_path)
    if completed.returncode != 0:
        payload["error"] = completed.stderr.strip() or completed.stdout.strip() or "tiny gpu smoke failed"
    return payload


def build_parser() -> argparse.ArgumentParser:
    common = _build_common_parser()
    nested_common = _build_common_parser(suppress_defaults=True)

    parser = argparse.ArgumentParser(
        prog="python -m lab.cli",
        description="Autoresearch Lab command line interface",
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", parents=[common], help="create managed roots and initialize the lab")
    bootstrap.set_defaults(handler=_cmd_bootstrap)

    preflight = subparsers.add_parser("preflight", parents=[common], help="run non-invasive environment checks")
    preflight.add_argument("--campaign")
    preflight.add_argument("--benchmark-backends", action="store_true")
    preflight.set_defaults(handler=_cmd_preflight)

    smoke = subparsers.add_parser("smoke", parents=[common], help="run a quick health check")
    smoke.add_argument("--campaign")
    smoke.add_argument("--gpu", action="store_true", help="include GPU checks")
    smoke.set_defaults(handler=_cmd_smoke)

    campaign = subparsers.add_parser("campaign", parents=[common], help="campaign management commands")
    campaign_subparsers = campaign.add_subparsers(dest="campaign_command", required=True)
    campaign_list = campaign_subparsers.add_parser("list", parents=[nested_common], help="list campaigns")
    campaign_list.set_defaults(handler=_cmd_campaign_list)

    campaign_show = campaign_subparsers.add_parser("show", parents=[nested_common], help="show one campaign manifest")
    campaign_show.add_argument("--campaign")
    campaign_show.set_defaults(handler=_cmd_campaign_show)

    campaign_build = campaign_subparsers.add_parser("build", parents=[nested_common], help="build campaign assets")
    campaign_build.add_argument("--campaign")
    campaign_build.add_argument("--source-dir", type=Path)
    campaign_build.set_defaults(handler=_cmd_campaign_build)

    campaign_verify = campaign_subparsers.add_parser("verify", parents=[nested_common], help="verify campaign assets")
    campaign_verify.add_argument("--campaign")
    campaign_verify.set_defaults(handler=_cmd_campaign_verify)

    campaign_queue = campaign_subparsers.add_parser("queue", parents=[nested_common], help="preview or apply structured queue fill")
    campaign_queue.add_argument("--campaign")
    campaign_queue.add_argument("--count", type=int, default=5)
    campaign_queue.add_argument("--lane", choices=["scout", "main", "confirm"])
    campaign_queue.add_argument("--family", choices=GENERATABLE_FAMILIES)
    campaign_queue.add_argument("--apply", action="store_true")
    campaign_queue.set_defaults(handler=_cmd_campaign_queue)

    run_parser = subparsers.add_parser("run", parents=[common], help="execute one proposal")
    run_parser.add_argument("--campaign")
    run_parser.add_argument("--lane", choices=["scout", "main", "confirm"])
    run_parser.add_argument("--family", choices=GENERATABLE_FAMILIES)
    run_parser.add_argument("--proposal", type=Path)
    run_parser.add_argument("--proposal-id")
    run_parser.add_argument("--generate", choices=["structured"])
    run_parser.add_argument("--target-command")
    run_parser.add_argument("--target-command-json")
    run_parser.add_argument("--time-budget-seconds", type=int)
    run_parser.add_argument("--seed", type=int)
    run_parser.add_argument("--backend")
    run_parser.add_argument("--device-profile")
    run_parser.set_defaults(handler=_cmd_run)

    inspect_parser = subparsers.add_parser("inspect", parents=[common], help="inspect campaigns, proposals, or experiments")
    inspect_parser.add_argument("--experiment")
    inspect_parser.add_argument("--proposal")
    inspect_parser.add_argument("--campaign")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    replay_parser = subparsers.add_parser("replay", parents=[common], help="re-run an existing manifest or proposal")
    replay_parser.add_argument("--experiment")
    replay_parser.add_argument("--proposal")
    replay_parser.add_argument("--target-command")
    replay_parser.add_argument("--target-command-json")
    replay_parser.add_argument("--time-budget-seconds", type=int)
    replay_parser.add_argument("--seed", type=int)
    replay_parser.add_argument("--backend")
    replay_parser.add_argument("--device-profile")
    replay_parser.set_defaults(handler=_cmd_replay)

    score_parser = subparsers.add_parser("score", parents=[common], help="explain or recompute scoring decisions")
    score_parser.add_argument("--experiment", required=True)
    score_parser.set_defaults(handler=_cmd_score)

    export_parser = subparsers.add_parser("export-code-proposal", parents=[common], help="export a code-lane task pack")
    export_parser.add_argument("--proposal-id", required=True)
    export_parser.set_defaults(handler=_cmd_export_code_proposal)

    import_parser = subparsers.add_parser("import-code-proposal", parents=[common], help="import a returned code-lane patch or worktree")
    import_parser.add_argument("--proposal-id", required=True)
    import_parser.add_argument("--patch-path", type=Path)
    import_parser.add_argument("--worktree-path", type=Path)
    import_parser.set_defaults(handler=_cmd_import_code_proposal)

    night_parser = subparsers.add_parser("night", parents=[common], help="run an unattended night session")
    night_parser.add_argument("--campaign")
    night_parser.add_argument("--hours", type=float, default=8.0)
    night_parser.add_argument("--max-runs", type=int)
    night_parser.add_argument("--allow-confirm", action="store_true")
    night_parser.add_argument("--seed-policy", choices=["fixed", "mixed"], default="fixed")
    night_parser.add_argument("--target-command")
    night_parser.add_argument("--target-command-json")
    night_parser.add_argument("--backend")
    night_parser.add_argument("--device-profile")
    night_parser.set_defaults(handler=_cmd_night)

    report_parser = subparsers.add_parser("report", parents=[common], help="generate reports")
    report_parser.add_argument("--campaign")
    report_parser.add_argument("--date")
    report_parser.add_argument("--from", dest="from_timestamp")
    report_parser.add_argument("--to", dest="to_timestamp")
    report_parser.set_defaults(handler=_cmd_report)

    doctor_parser = subparsers.add_parser("doctor", parents=[common], help="diagnose ledger and artifact health")
    doctor_parser.add_argument("--campaign")
    doctor_parser.set_defaults(handler=_cmd_doctor)

    cleanup_parser = subparsers.add_parser("cleanup", parents=[common], help="remove discardable artifacts")
    cleanup_parser.add_argument("--campaign")
    cleanup_parser.add_argument("--dry-run", action="store_true")
    cleanup_parser.add_argument("--apply", action="store_true")
    cleanup_parser.set_defaults(handler=_cmd_cleanup)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        payload = {"ok": False, "message": "interrupted"}
        _emit(payload, getattr(args, "json", False))
        return EXIT_INTERRUPTED
    except SettingsError as exc:
        payload = {"ok": False, "error": str(exc)}
        _emit(payload, getattr(args, "json", False))
        return EXIT_USER_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
