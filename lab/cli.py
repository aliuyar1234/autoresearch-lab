from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from .backends import (
    autotune_runtime,
    available_backend_candidates,
    backend_blacklist_path,
    backend_cache_path,
    detect_device_profile,
    select_backend,
    shape_family_for_run,
)
from research.dense_gpt.search_space import resolve_dense_config

from .campaigns import build_campaign, list_campaigns, load_campaign, verify_campaign
from .cleanup import run_cleanup
from .code_proposals import CodeProposalExportError, CodeProposalImportError, code_proposal_ready, export_code_proposal_pack, import_code_proposal_result
from .doctor import run_doctor
from .ledger.db import apply_migrations, connect, list_schema_versions
from .ledger.queries import (
    get_experiment,
    get_memory_records_by_ids,
    get_latest_daily_report,
    get_proposal,
    get_retrieval_event,
    get_validation_review,
    list_archive_rows,
    list_campaign_experiments,
    list_campaign_proposals,
    list_daily_reports,
    list_memory_records,
    list_prior_experiments,
    list_validation_reviews,
    upsert_campaign,
    upsert_proposal,
)
from .memory import backfill_memory, persist_proposal_memory_state
from .night import run_night_session
from .paths import build_paths, ensure_managed_roots, missing_repo_markers, resolve_managed_path, stringify_paths
from .preflight import run_preflight
from .proposals import normalize_proposal_payload
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
from .validation import run_noise_probe, run_validation_review

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


def _command_name(args: argparse.Namespace) -> str:
    command = str(getattr(args, "command", "cli"))
    if command == "campaign" and getattr(args, "campaign_command", None):
        return f"campaign.{args.campaign_command}"
    if command == "memory" and getattr(args, "memory_command", None):
        return f"memory.{args.memory_command}"
    return command


def _with_envelope(
    payload: dict[str, object],
    *,
    command: str,
    status: str | None = None,
    message: str,
) -> dict[str, object]:
    data = dict(payload)
    ok = bool(data.get("ok", True))
    data["ok"] = ok
    data["command"] = command
    data["status"] = str(status or data.get("status") or ("ok" if ok else "error"))
    data["message"] = message
    return data


def _respond(
    args: argparse.Namespace,
    payload: dict[str, object],
    *,
    status: str | None = None,
    message: str,
    command: str | None = None,
) -> None:
    _emit(
        _with_envelope(
            payload,
            command=command or _command_name(args),
            status=status,
            message=message,
        ),
        bool(getattr(args, "json", False)),
    )


def _sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _format_metric(name: object, value: object) -> str | None:
    if value is None:
        return None
    label = str(name or "metric")
    try:
        return f"{label}={float(value):.6f}"
    except (TypeError, ValueError):
        return f"{label}={value}"


def _format_bytes(value: object) -> str:
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _sample_items(items: object, *, limit: int = 2, key: str | None = None) -> list[str]:
    if not isinstance(items, list):
        return []
    sampled: list[str] = []
    for item in items:
        if len(sampled) >= limit:
            break
        if key is not None and isinstance(item, dict):
            value = item.get(key)
        else:
            value = item
        if value in (None, "", [], {}):
            continue
        sampled.append(str(value))
    return sampled


def _generic_human_lines(payload: dict[str, object]) -> list[str]:
    lines = [_sentence(str(payload.get("message") or "command completed"))]
    for label, key in (
        ("Status", "status"),
        ("Campaign", "campaign_id"),
        ("Experiment", "experiment_id"),
        ("Proposal", "proposal_id"),
        ("Artifacts", "artifact_root"),
        ("Summary", "summary_path"),
        ("Report", "report_path"),
        ("Error", "error"),
    ):
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        lines.append(f"{label}: {value}")
    return lines


def _bootstrap_human_lines(payload: dict[str, object]) -> list[str]:
    created_roots = payload.get("created_roots")
    created_count = len(created_roots) if isinstance(created_roots, list) else 0
    db_state = "created" if payload.get("db_created") else "already existed"
    roots_line = f"Created {created_count} managed roots." if created_count else "Managed roots already existed."
    return [
        "Bootstrap ready.",
        f"{roots_line} Database {db_state} at {payload.get('db_path')}.",
        f"Env file: {payload.get('env_file')}",
    ]


def _preflight_human_lines(payload: dict[str, object]) -> list[str]:
    campaign = str(payload.get("campaign_id") or "repo")
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    missing_assets = payload.get("missing_assets") if isinstance(payload.get("missing_assets"), list) else []
    device = str(payload.get("device") or "not detected")
    profile = str(payload.get("device_profile") or "unknown profile")
    lines = [
        f"Preflight {'passed' if payload.get('ok') else 'found issues'} for {campaign}.",
        f"Device: {device} ({profile}). Warnings: {len(warnings)}. Missing assets: {len(missing_assets)}.",
    ]
    if warnings:
        lines.append(f"First warning: {warnings[0]}")
    if missing_assets:
        lines.append(f"Missing asset: {missing_assets[0]}")
    return lines


def _campaign_build_human_lines(payload: dict[str, object]) -> list[str]:
    return [
        f"Campaign assets built for {payload.get('campaign_id')}.",
        f"Asset root: {payload.get('asset_root')}",
        f"Packed manifest: {payload.get('packed_manifest')}",
    ]


def _run_human_lines(payload: dict[str, object]) -> list[str]:
    status = str(payload.get("status") or "unknown").replace("_", " ")
    lines = [
        f"Run {status} for {payload.get('experiment_id')}.",
        f"Proposal: {payload.get('proposal_id')} ({payload.get('proposal_family')}/{payload.get('proposal_kind')}).",
    ]
    metric = _format_metric(payload.get("primary_metric_name"), payload.get("primary_metric_value"))
    disposition = payload.get("disposition")
    validation_state = payload.get("validation_state")
    if metric:
        lines.append(f"Metric: {metric}.")
    if disposition not in (None, "") or validation_state not in (None, ""):
        lines.append(f"Disposition: {disposition or 'n/a'}. Validation: {validation_state or 'n/a'}.")
    if payload.get("crash_class"):
        lines.append(f"Crash class: {payload.get('crash_class')}")
    lines.append(f"Summary: {payload.get('summary_path')}")
    return lines


def _night_human_lines(payload: dict[str, object]) -> list[str]:
    status = str(payload.get("status") or "unknown").replace("_", " ")
    lines = [
        f"Night session {status} for {payload.get('campaign_id')}.",
        f"Runs: {payload.get('run_count', 0)}. Promotions: {payload.get('promoted_count', 0)}. Failures: {payload.get('failed_count', 0)}.",
    ]
    if payload.get("session_started_at") and payload.get("session_ended_at"):
        lines.append(f"Window: {payload.get('session_started_at')} -> {payload.get('session_ended_at')}")
    if payload.get("report_path"):
        lines.append(f"Report: {payload.get('report_path')}")
    return lines


def _report_human_lines(payload: dict[str, object]) -> list[str]:
    lines = [
        f"Report generated for {payload.get('campaign_id')} ({payload.get('report_date')}).",
        f"Runs: {payload.get('run_count', 0)}. Promotions: {payload.get('promoted_count', 0)}. Failures: {payload.get('failed_count', 0)}.",
    ]
    if payload.get("window_started_at") or payload.get("window_ended_at"):
        lines.append(f"Window: {payload.get('window_started_at')} -> {payload.get('window_ended_at')}")
    if payload.get("report_path"):
        lines.append(f"Report: {payload.get('report_path')}")
    return lines


def _doctor_human_lines(payload: dict[str, object]) -> list[str]:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    findings = payload.get("findings")
    lines = [
        "Doctor is clean." if payload.get("ok") else "Doctor found issues.",
        f"Errors: {counts.get('error', 0)}. Warnings: {counts.get('warning', 0)}. Info: {counts.get('info', 0)}.",
    ]
    if isinstance(findings, list):
        for message in _sample_items(findings, key="message"):
            lines.append(f"Action: {message}")
    return lines


def _cleanup_human_lines(payload: dict[str, object]) -> list[str]:
    mode = "Cleanup applied." if payload.get("apply") else "Cleanup dry run."
    lines = [
        mode,
        (
            f"Candidates: {payload.get('candidate_count', 0)}. "
            f"Reclaimable: {_format_bytes(payload.get('candidate_bytes'))}. "
            f"Skipped: {payload.get('skipped_count', 0)}."
        ),
    ]
    path_source = payload.get("deleted_paths") if payload.get("apply") else payload.get("candidates")
    for path in _sample_items(path_source, key="path"):
        lines.append(f"Path: {path}")
    return lines


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    command = str(payload.get("command") or "")
    if command == "bootstrap":
        lines = _bootstrap_human_lines(payload)
    elif command == "preflight":
        lines = _preflight_human_lines(payload)
    elif command == "campaign.build":
        lines = _campaign_build_human_lines(payload)
    elif command == "run":
        lines = _run_human_lines(payload)
    elif command == "night":
        lines = _night_human_lines(payload)
    elif command == "report":
        lines = _report_human_lines(payload)
    elif command == "doctor":
        lines = _doctor_human_lines(payload)
    elif command == "cleanup":
        lines = _cleanup_human_lines(payload)
    else:
        lines = _generic_human_lines(payload)
    for line in lines:
        if line:
            print(line)


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
    db_created = apply_migrations(paths.db_path, paths.sql_root)
    schema_versions = list_schema_versions(paths.db_path)

    env_created = False
    if not paths.env_file.exists():
        paths.env_file.write_text(_lab_env_template(settings), encoding="utf-8")
        env_created = True

    payload = {
        "ok": True,
        "repo_root": str(paths.repo_root),
        "created_roots": stringify_paths(created_roots),
        "created_root_count": len(created_roots),
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
    _respond(args, payload, status="ready", message="initialized managed lab roots")
    return EXIT_SUCCESS


def _cmd_preflight(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    result = run_preflight(
        paths,
        campaign_id=getattr(args, "campaign", None),
        benchmark_backends=bool(getattr(args, "benchmark_backends", False)),
    )
    payload = result.to_dict()
    _respond(
        args,
        payload,
        status="ok" if result.ok else "issues_found",
        message="checked local lab prerequisites",
    )
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
    _respond(
        args,
        payload,
        status="ok" if smoke_ok else "issues_found",
        message="ran smoke checks",
    )
    return EXIT_SUCCESS if smoke_ok else EXIT_PREFLIGHT_FAILURE


def _cmd_campaign_list(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = {
        "ok": True,
        "campaigns": list_campaigns(paths),
    }
    _respond(args, payload, status="ok", message=f"listed {len(payload['campaigns'])} campaigns")
    return EXIT_SUCCESS


def _cmd_campaign_show(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign show requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = load_campaign(paths, args.campaign)
    _respond(args, payload, status="ok", message=f"loaded campaign {args.campaign}")
    return EXIT_SUCCESS


def _cmd_campaign_build(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign build requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = build_campaign(paths, args.campaign, source_dir=getattr(args, "source_dir", None))
    _respond(args, payload, status="built", message=f"built campaign assets for {args.campaign}")
    return EXIT_SUCCESS


def _cmd_campaign_verify(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign verify requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = verify_campaign(paths, args.campaign)
    _respond(
        args,
        payload,
        status="verified" if payload["ok"] else "issues_found",
        message=f"verified campaign assets for {args.campaign}",
    )
    return EXIT_SUCCESS if payload["ok"] else EXIT_PREFLIGHT_FAILURE


def _cmd_campaign_queue(args: argparse.Namespace) -> int:
    if not args.campaign:
        raise SettingsError("campaign queue requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
                proposal = normalize_proposal_payload(proposal)
                validate_payload(proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
                upsert_proposal(connection, proposal, updated_at=proposal["created_at"])
                persist_proposal_memory_state(connection, paths=paths, proposal=proposal)
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
    _respond(
        args,
        payload,
        status="queued" if bool(getattr(args, "apply", False)) else "planned",
        message="queued structured proposals" if bool(getattr(args, "apply", False)) else "planned structured queue entries",
    )
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


def _load_campaign(paths, campaign_id: str) -> dict[str, object]:
    manifest_path = paths.campaigns_root / campaign_id / "campaign.json"
    if not manifest_path.exists():
        raise SettingsError(f"campaign manifest not found: {manifest_path}")
    payload = read_json(manifest_path)
    validate_payload(payload, load_schema(paths.schemas_root / "campaign.schema.json"))
    return payload


def _torch_runtime_versions() -> tuple[str, str | None]:
    torch_version = "unavailable"
    cuda_version = None
    try:
        import torch

        torch_version = str(getattr(torch, "__version__", "unavailable"))
        cuda_version = getattr(torch.version, "cuda", None)
    except Exception:
        pass
    return torch_version, cuda_version


def _select_backend_for_resolved_config(paths, campaign: dict[str, object], resolved_config: dict[str, object], detected_profile):
    shape = shape_family_for_run(campaign, resolved_config, detected_profile, purpose="train")
    torch_version, cuda_version = _torch_runtime_versions()
    selection = select_backend(
        cache_path=backend_cache_path(paths),
        blacklist_path=backend_blacklist_path(paths),
        candidates=available_backend_candidates(detected_profile),
        shape=shape,
        device_profile=detected_profile,
        cuda_version=cuda_version,
        torch_version=torch_version,
        compile_enabled=bool(resolved_config["runtime"].get("compile_enabled", True)),
    )
    return selection.backend, selection


def _experiment_runtime_details(paths, row: dict[str, object]) -> dict[str, object] | None:
    artifact_root = row.get("artifact_root")
    if not artifact_root:
        return None
    root = resolve_managed_path(paths, str(artifact_root))
    manifest_path = root / "manifest.json"
    config_path = root / "config.json"
    if not manifest_path.exists():
        return None
    manifest = read_json(manifest_path)
    config_payload = read_json(config_path) if config_path.exists() else None
    return {
        "artifact_root": str(root),
        "manifest_path": str(manifest_path),
        "config_path": str(config_path) if config_path.exists() else None,
        "runtime_defaults": manifest.get("runtime_defaults"),
        "runtime_overlay": manifest.get("runtime_overlay"),
        "runtime_effective": manifest.get("runtime_effective"),
        "autotune": manifest.get("autotune"),
        "runtime_autotune_from_config": (config_payload or {}).get("runtime", {}).get("autotune")
        if isinstance(config_payload, dict)
        else None,
    }


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
        payload = normalize_proposal_payload(payload)
        validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
        return payload
    if getattr(args, "proposal", None):
        payload = normalize_proposal_payload(read_json(Path(args.proposal)))
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
        payload = normalize_proposal_payload(json.loads(row["proposal_json"]))
        validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
        return payload
    raise SettingsError("run requires --proposal or --proposal-id")


def _time_budget_for_lane(campaign: dict[str, object], lane: str) -> int:
    budgets = campaign["budgets"]
    key = f"{lane}_seconds"
    return int(budgets[key])


def _default_run_purpose(proposal: dict[str, object], *, is_replay: bool) -> str:
    if is_replay:
        return "replay"
    if str(proposal.get("family") or "") == "baseline":
        return "baseline"
    return "search"


def _cmd_autotune(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("autotune requires --campaign")
    if not getattr(args, "all_lanes", False) and not getattr(args, "lane", None):
        raise SettingsError("autotune requires --lane or --all-lanes")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    ensure_managed_roots(paths)
    campaign = _load_campaign(paths, str(args.campaign))
    lanes = ["scout", "main", "confirm"] if bool(getattr(args, "all_lanes", False)) else [str(args.lane)]
    detected_profile = detect_device_profile(getattr(args, "device_profile", None))
    resolved_config = resolve_dense_config(campaign, {}, device_profile=detected_profile)
    backend = getattr(args, "backend", None)
    if backend is None:
        backend, _ = _select_backend_for_resolved_config(paths, campaign, resolved_config, detected_profile)

    results = [
        autotune_runtime(
            paths,
            campaign=campaign,
            lane=lane_name,
            device_profile=detected_profile,
            backend=str(backend),
            resolved_config=resolved_config,
            force=bool(getattr(args, "force", False)),
        ).to_dict()
        for lane_name in lanes
    ]
    if len(results) == 1:
        payload = dict(results[0])
        payload["ok"] = bool(payload.get("winner"))
        payload["candidates"] = payload.get("candidates", [])
    else:
        payload = {
            "ok": all(bool(item.get("winner")) for item in results),
            "campaign_id": str(campaign["campaign_id"]),
            "lanes": lanes,
            "device_profile": detected_profile.profile_id,
            "backend": str(backend),
            "results": results,
        }
    _respond(
        args,
        payload,
        status="tuned" if payload.get("ok") else "no_winner",
        message="resolved runtime autotune overlays",
    )
    return EXIT_SUCCESS if payload.get("ok") else EXIT_PREFLIGHT_FAILURE


def _cmd_run(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)

    proposal = _load_proposal_from_args(args, paths)
    if proposal.get("kind") == "code_patch" and not code_proposal_ready(proposal):
        raise SettingsError("code_patch proposal is not ready to run; import a returned patch or worktree first")
    campaign = _load_campaign(paths, str(proposal["campaign_id"]))
    seed = int(getattr(args, "seed", None) or campaign["budgets"].get("replication_seeds", [42])[0])
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(proposal["lane"])))
    eval_split = str(getattr(args, "eval_split", None) or "search_val")
    run_purpose = str(getattr(args, "run_purpose", None) or _default_run_purpose(proposal, is_replay=False))
    result = execute_experiment(
        paths=paths,
        proposal=proposal,
        campaign=campaign,
        target_command_template=_parse_target_command(args),
        seed=seed,
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
        eval_split=eval_split,
        run_purpose=run_purpose,
    )
    summary_payload = read_json(result.summary_path) if result.summary_path.exists() else {}

    payload = {
        "ok": result.status == "completed" and not result.schema_failed,
        "experiment_id": result.experiment_id,
        "proposal_id": result.proposal_id,
        "proposal_family": proposal["family"],
        "proposal_kind": proposal["kind"],
        "status": result.status,
        "eval_split": eval_split,
        "run_purpose": run_purpose,
        "crash_class": result.crash_class,
        "artifact_root": str(result.artifact_root),
        "summary_path": str(result.summary_path),
        "primary_metric_name": summary_payload.get("primary_metric_name") if isinstance(summary_payload, dict) else None,
        "primary_metric_value": result.primary_metric_value,
        "disposition": summary_payload.get("disposition") if isinstance(summary_payload, dict) else None,
        "validation_state": summary_payload.get("validation_state") if isinstance(summary_payload, dict) else None,
        "schema_failed": result.schema_failed,
    }
    _respond(args, payload, message="executed one proposal")
    if result.schema_failed:
        return EXIT_SCHEMA_FAILURE
    return EXIT_SUCCESS if result.status == "completed" else EXIT_RUN_FAILURE


def _cmd_replay(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)

    proposal, replay_source_experiment_id = load_replay_proposal(
        paths,
        experiment_id=getattr(args, "experiment", None),
        proposal_id=getattr(args, "proposal", None),
    )
    campaign = _load_campaign(paths, str(proposal["campaign_id"]))
    seed = int(getattr(args, "seed", None) or campaign["budgets"].get("replication_seeds", [42])[0])
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(proposal["lane"])))
    eval_split = str(getattr(args, "eval_split", None) or "search_val")
    run_purpose = str(getattr(args, "run_purpose", None) or _default_run_purpose(proposal, is_replay=True))

    result = execute_experiment(
        paths=paths,
        proposal=proposal,
        campaign=campaign,
        target_command_template=_parse_target_command(args),
        seed=seed,
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
        eval_split=eval_split,
        run_purpose=run_purpose,
        replay_source_experiment_id=replay_source_experiment_id,
        score_result=False,
    )

    payload = {
        "ok": result.status == "completed" and not result.schema_failed,
        "experiment_id": result.experiment_id,
        "proposal_id": result.proposal_id,
        "status": result.status,
        "eval_split": eval_split,
        "run_purpose": run_purpose,
        "artifact_root": str(result.artifact_root),
        "summary_path": str(result.summary_path),
        "source_experiment_id": replay_source_experiment_id,
    }
    _respond(args, payload, message="replayed one proposal")
    if result.schema_failed:
        return EXIT_SCHEMA_FAILURE
    return EXIT_SUCCESS if result.status == "completed" else EXIT_RUN_FAILURE


def _cmd_export_code_proposal(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
        evidence_ids = [str(item.get("memory_id")) for item in proposal.get("evidence", []) if str(item.get("memory_id") or "")]
        evidence_records = get_memory_records_by_ids(connection, evidence_ids)
        retrieval_event = None
        if proposal.get("retrieval_event_id"):
            retrieval_event = get_retrieval_event(connection, str(proposal["retrieval_event_id"]))
    finally:
        connection.close()

    try:
        payload = export_code_proposal_pack(
            paths=paths,
            campaign=campaign,
            proposal=proposal,
            best_comparator=best_comparator,
            parent_experiments=parent_experiments,
            evidence_records=evidence_records,
            retrieval_event=retrieval_event,
        )
    except CodeProposalExportError as exc:
        raise SettingsError(str(exc)) from exc
    _respond(args, payload, status="exported", message=f"exported code proposal pack for {args.proposal_id}")
    return EXIT_SUCCESS


def _cmd_import_code_proposal(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
        updated_proposal = normalize_proposal_payload(updated_proposal)
        validate_payload(updated_proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
        upsert_proposal(connection, updated_proposal, updated_at=utc_now_iso())
        persist_proposal_memory_state(connection, paths=paths, proposal=updated_proposal)
        connection.commit()
    finally:
        connection.close()
    _respond(args, payload, status="imported", message=f"imported code proposal result for {args.proposal_id}")
    return EXIT_SUCCESS


def _cmd_report(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("report requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
    payload = {
        **payload,
        "report_path": payload["artifact_paths"]["report_md"],
        "report_json_path": payload["artifact_paths"]["report_json"],
    }
    _respond(args, payload, status="generated", message="generated one report bundle")
    return EXIT_SUCCESS


def _cmd_memory_backfill(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("memory backfill requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
    campaign = _load_campaign(paths, str(args.campaign))
    connection = connect(paths.db_path)
    try:
        payload = backfill_memory(
            connection,
            paths=paths,
            campaign=campaign,
            experiments=list_campaign_experiments(connection, str(args.campaign)),
            validation_reviews=list_validation_reviews(connection, campaign_id=str(args.campaign)),
            reports=list_daily_reports(connection, str(args.campaign)),
        )
        connection.commit()
    finally:
        connection.close()
    _respond(
        args,
        {
            "ok": True,
            "campaign_id": str(args.campaign),
            **payload,
        },
        status="backfilled",
        message=f"backfilled memory for {args.campaign}",
    )
    return EXIT_SUCCESS


def _cmd_memory_inspect(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("memory inspect requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
    campaign = _load_campaign(paths, str(args.campaign))
    connection = connect(paths.db_path)
    try:
        records = list_memory_records(
            connection,
            campaign_id=str(args.campaign),
            comparability_group=str(campaign.get("comparability_group") or ""),
            limit=int(getattr(args, "limit", 20)),
        )
    finally:
        connection.close()
    _respond(
        args,
        {
            "ok": True,
            "campaign_id": str(args.campaign),
            "count": len(records),
            "records": records,
        },
        status="ok",
        message=f"listed {len(records)} memory records",
    )
    return EXIT_SUCCESS


def _cmd_validate(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
    source_experiment_id = str(args.experiment)
    connection = connect(paths.db_path)
    try:
        source = get_experiment(connection, source_experiment_id)
        if not source:
            raise SettingsError(f"experiment not found: {source_experiment_id}")
        campaign = _load_campaign(paths, str(source["campaign_id"]))
    finally:
        connection.close()
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(source["lane"])))
    review = run_validation_review(
        paths=paths,
        campaign=campaign,
        source_experiment_id=source_experiment_id,
        mode=str(args.mode),
        target_command_template=_parse_target_command(args),
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
        dry_run=bool(getattr(args, "dry_run", False)),
        reuse_comparator_replays=bool(getattr(args, "reuse_comparator_replays", False)),
        force_replay=bool(getattr(args, "force_replay", False)),
    )
    payload = review.to_dict()
    _respond(
        args,
        payload,
        status=str(payload.get("decision") or "completed"),
        message=f"reviewed candidate on {args.mode} validation",
    )
    if str(review.decision) == "failed":
        return EXIT_RUN_FAILURE
    return EXIT_SUCCESS


def _cmd_noise(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("noise requires --campaign")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
    campaign = _load_campaign(paths, str(args.campaign))
    time_budget_seconds = int(getattr(args, "time_budget_seconds", None) or _time_budget_for_lane(campaign, str(args.lane)))
    payload = run_noise_probe(
        paths=paths,
        campaign=campaign,
        lane=str(args.lane),
        count=int(args.count),
        seed_start=int(getattr(args, "seed_start", 42)),
        target_command_template=_parse_target_command(args),
        time_budget_seconds=time_budget_seconds,
        device_profile=getattr(args, "device_profile", None),
        backend=getattr(args, "backend", None),
    )
    _respond(args, payload.to_dict(), status="measured", message=f"measured noise on {args.lane} lane")
    return EXIT_SUCCESS


def _cmd_cleanup(args: argparse.Namespace) -> int:
    if bool(getattr(args, "apply", False)) and bool(getattr(args, "dry_run", False)):
        raise SettingsError("cleanup accepts either --apply or --dry-run, not both")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
    cleanup_status = str(payload.get("status") or ("applied" if bool(getattr(args, "apply", False)) else "dry_run"))
    cleanup_message = "cleanup found nothing pruneable" if cleanup_status == "clean" else ("applied cleanup" if bool(getattr(args, "apply", False)) else "planned cleanup")
    _respond(
        args,
        payload,
        status=cleanup_status,
        message=cleanup_message,
    )
    return EXIT_SUCCESS


def _cmd_doctor(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    payload = run_doctor(paths, campaign_id=getattr(args, "campaign", None))
    _respond(
        args,
        payload,
        status="clean" if payload.get("ok") else "issues_found",
        message="checked ledger and artifact health",
    )
    return EXIT_SUCCESS if payload.get("ok") else EXIT_PREFLIGHT_FAILURE


def _cmd_night(args: argparse.Namespace) -> int:
    if not getattr(args, "campaign", None):
        raise SettingsError("night requires --campaign")
    if float(getattr(args, "hours", 8.0)) <= 0 and getattr(args, "max_runs", None) is None:
        raise SettingsError("night requires positive --hours or --max-runs")
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
    report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    payload = {
        **payload,
        "report_path": report_payload.get("artifact_paths", {}).get("report_md") if isinstance(report_payload, dict) else None,
        "report_json_path": report_payload.get("artifact_paths", {}).get("report_json") if isinstance(report_payload, dict) else None,
        "promoted_count": report_payload.get("promoted_count", 0) if isinstance(report_payload, dict) else 0,
        "failed_count": report_payload.get("failed_count", 0) if isinstance(report_payload, dict) else 0,
    }
    night_status = str(payload.get("status") or "completed")
    night_message = {
        "preflight_failed": "night session stopped at preflight",
        "interrupted": "night session interrupted; continuation hint included",
        "idle": "night session found no queued work",
    }.get(night_status, "completed one night session")
    _respond(args, payload, status=night_status, message=night_message)
    if payload.get("status") == "interrupted":
        return EXIT_INTERRUPTED
    return EXIT_SUCCESS if payload.get("ok") else EXIT_PREFLIGHT_FAILURE


def _cmd_inspect(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
                "eval_split": row.get("eval_split"),
                "run_purpose": row.get("run_purpose"),
                "validation_state": row.get("validation_state"),
                "validation_review_id": row.get("validation_review_id"),
                "idea_signature": row.get("idea_signature"),
                "disposition": row["disposition"],
                "crash_class": row["crash_class"],
                "proposal_family": row["proposal_family"],
                "proposal_kind": row["proposal_kind"],
                "primary_metric_name": row["primary_metric_name"],
                "primary_metric_value": row["primary_metric_value"],
                "artifact_root": row["artifact_root"],
                "summary_path": row["summary_path"],
            }
            proposal_payload = None
            if row.get("proposal_id"):
                proposal_row = get_proposal(connection, str(row["proposal_id"]))
                if proposal_row and proposal_row.get("proposal_json"):
                    proposal_payload = normalize_proposal_payload(json.loads(proposal_row["proposal_json"]))
            if proposal_payload is not None:
                payload["proposal_evidence_summary"] = {
                    "idea_signature": proposal_payload.get("idea_signature"),
                    "retrieval_event_id": proposal_payload.get("retrieval_event_id"),
                    "evidence_count": len(proposal_payload.get("evidence", [])),
                    "warning_count": sum(1 for item in proposal_payload.get("evidence", []) if item.get("role") == "warning"),
                    "anchor_experiment_ids": proposal_payload.get("generation_context", {}).get("anchor_experiment_ids", []),
                }
            runtime_details = _experiment_runtime_details(paths, row)
            if runtime_details is not None:
                payload["runtime_execution"] = runtime_details
            if row.get("validation_review_id"):
                payload["validation_review"] = get_validation_review(connection, str(row["validation_review_id"]))
        elif args.proposal:
            row = get_proposal(connection, args.proposal)
            if not row:
                raise SettingsError(f"proposal not found: {args.proposal}")
            proposal_payload = normalize_proposal_payload(json.loads(row["proposal_json"]))
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
                "idea_signature": proposal_payload.get("idea_signature"),
                "mutation_paths": proposal_payload.get("mutation_paths", []),
                "retrieval_event_id": proposal_payload.get("retrieval_event_id"),
                "evidence": proposal_payload.get("evidence", []),
                "generation_context": proposal_payload.get("generation_context", {}),
                "config_fingerprint": proposal_payload.get("config_fingerprint"),
                "code_patch_imported": bool(isinstance(proposal_payload.get("code_patch"), dict) and proposal_payload["code_patch"].get("import_root")),
                "code_patch_import_root": proposal_payload.get("code_patch", {}).get("import_root")
                if isinstance(proposal_payload.get("code_patch"), dict)
                else None,
                "code_patch_patch_path": proposal_payload.get("code_patch", {}).get("patch_path")
                if isinstance(proposal_payload.get("code_patch"), dict)
                else None,
                "code_patch_diff_stats": proposal_payload.get("code_patch", {}).get("diff_stats")
                if isinstance(proposal_payload.get("code_patch"), dict)
                else None,
                "code_patch_evidence_memory_ids": proposal_payload.get("code_patch", {}).get("evidence_memory_ids")
                if isinstance(proposal_payload.get("code_patch"), dict)
                else None,
            }
            if proposal_payload.get("retrieval_event_id"):
                payload["retrieval_event"] = get_retrieval_event(connection, str(proposal_payload["retrieval_event_id"]))
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
                    "memory_summary": report_payload.get("memory_summary", {}),
                }
        else:
            raise SettingsError("inspect requires --experiment, --proposal, or --campaign")
    finally:
        connection.close()
    _respond(args, payload, status=str(payload.get("status") or "ok"), message=f"inspected {payload.get('kind', 'record')}")
    return EXIT_SUCCESS


def _cmd_score(args: argparse.Namespace) -> int:
    settings = _load_settings_from_args(args)
    paths = build_paths(settings)
    apply_migrations(paths.db_path, paths.sql_root)
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
        "eval_split": row.get("eval_split"),
        "run_purpose": row.get("run_purpose"),
        "validation_state": row.get("validation_state"),
        "validation_review_id": row.get("validation_review_id"),
        "crash_class": row["crash_class"],
        "primary_metric_name": row["primary_metric_name"],
        "primary_metric_value": row["primary_metric_value"],
        **explanation.to_dict(),
    }
    _respond(args, payload, message=f"scored experiment {row['experiment_id']}")
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
        "--eval-split",
        "search_val",
        "--run-purpose",
        "search",
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
        description="Autoresearch Lab: a local, single-GPU, CUDA-first, dense-model research lab.",
        epilog="Common path: bootstrap -> preflight -> campaign build -> run -> night -> report -> doctor -> cleanup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", parents=[common], help="create managed roots and initialize the lab")
    bootstrap.set_defaults(handler=_cmd_bootstrap)

    preflight = subparsers.add_parser("preflight", parents=[common], help="run non-invasive environment checks")
    preflight.add_argument("--campaign")
    preflight.add_argument("--benchmark-backends", action="store_true")
    preflight.set_defaults(handler=_cmd_preflight)

    campaign = subparsers.add_parser("campaign", parents=[common], help="campaign asset and queue commands")
    campaign_subparsers = campaign.add_subparsers(dest="campaign_command", required=True)

    campaign_build = campaign_subparsers.add_parser("build", parents=[nested_common], help="build campaign assets")
    campaign_build.add_argument("--campaign")
    campaign_build.add_argument("--source-dir", type=Path)
    campaign_build.set_defaults(handler=_cmd_campaign_build)

    campaign_queue = campaign_subparsers.add_parser("queue", parents=[nested_common], help="[advanced] preview or apply structured queue fill")
    campaign_queue.add_argument("--campaign")
    campaign_queue.add_argument("--count", type=int, default=5)
    campaign_queue.add_argument("--lane", choices=["scout", "main", "confirm"])
    campaign_queue.add_argument("--family", choices=GENERATABLE_FAMILIES)
    campaign_queue.add_argument("--apply", action="store_true")
    campaign_queue.set_defaults(handler=_cmd_campaign_queue)

    campaign_show = campaign_subparsers.add_parser("show", parents=[nested_common], help="[advanced] show one campaign manifest")
    campaign_show.add_argument("--campaign")
    campaign_show.set_defaults(handler=_cmd_campaign_show)

    campaign_verify = campaign_subparsers.add_parser("verify", parents=[nested_common], help="[advanced] verify campaign assets")
    campaign_verify.add_argument("--campaign")
    campaign_verify.set_defaults(handler=_cmd_campaign_verify)

    campaign_list = campaign_subparsers.add_parser("list", parents=[nested_common], help="[advanced] list campaigns")
    campaign_list.set_defaults(handler=_cmd_campaign_list)

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
    run_parser.add_argument("--eval-split", choices=["search_val", "audit_val", "locked_val"])
    run_parser.add_argument("--run-purpose", choices=["search", "confirm", "audit", "replay", "baseline", "noise_probe"])
    run_parser.set_defaults(handler=_cmd_run)

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

    doctor_parser = subparsers.add_parser("doctor", parents=[common], help="[maintenance] diagnose ledger and artifact health")
    doctor_parser.add_argument("--campaign")
    doctor_parser.set_defaults(handler=_cmd_doctor)

    cleanup_parser = subparsers.add_parser("cleanup", parents=[common], help="[maintenance] remove discardable artifacts")
    cleanup_parser.add_argument("--campaign")
    cleanup_parser.add_argument("--dry-run", action="store_true")
    cleanup_parser.add_argument("--apply", action="store_true")
    cleanup_parser.set_defaults(handler=_cmd_cleanup)

    inspect_parser = subparsers.add_parser("inspect", parents=[common], help="[advanced] inspect campaigns, proposals, or experiments")
    inspect_parser.add_argument("--experiment")
    inspect_parser.add_argument("--proposal")
    inspect_parser.add_argument("--campaign")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    replay_parser = subparsers.add_parser("replay", parents=[common], help="[advanced] re-run an existing manifest or proposal")
    replay_parser.add_argument("--experiment")
    replay_parser.add_argument("--proposal")
    replay_parser.add_argument("--target-command")
    replay_parser.add_argument("--target-command-json")
    replay_parser.add_argument("--time-budget-seconds", type=int)
    replay_parser.add_argument("--seed", type=int)
    replay_parser.add_argument("--backend")
    replay_parser.add_argument("--device-profile")
    replay_parser.add_argument("--eval-split", choices=["search_val", "audit_val", "locked_val"])
    replay_parser.add_argument("--run-purpose", choices=["search", "confirm", "audit", "replay", "baseline", "noise_probe"])
    replay_parser.set_defaults(handler=_cmd_replay)

    score_parser = subparsers.add_parser("score", parents=[common], help="[advanced] explain or recompute scoring decisions")
    score_parser.add_argument("--experiment", required=True)
    score_parser.set_defaults(handler=_cmd_score)

    validate_parser = subparsers.add_parser("validate", parents=[common], help="[advanced] run validation replays for a candidate experiment")
    validate_parser.add_argument("--experiment", required=True)
    validate_parser.add_argument("--mode", required=True, choices=["confirm", "audit", "locked"])
    validate_parser.add_argument("--dry-run", action="store_true")
    validate_parser.add_argument("--reuse-comparator-replays", action=argparse.BooleanOptionalAction, default=True)
    validate_parser.add_argument("--force-replay", action="store_true")
    validate_parser.add_argument("--target-command")
    validate_parser.add_argument("--target-command-json")
    validate_parser.add_argument("--time-budget-seconds", type=int)
    validate_parser.add_argument("--backend")
    validate_parser.add_argument("--device-profile")
    validate_parser.set_defaults(handler=_cmd_validate)

    noise_parser = subparsers.add_parser("noise", parents=[common], help="[advanced] run comparable baseline noise probes")
    noise_parser.add_argument("--campaign", required=True)
    noise_parser.add_argument("--lane", required=True, choices=["scout", "main", "confirm"])
    noise_parser.add_argument("--count", type=int, default=5)
    noise_parser.add_argument("--seed-start", type=int, default=42)
    noise_parser.add_argument("--target-command")
    noise_parser.add_argument("--target-command-json")
    noise_parser.add_argument("--time-budget-seconds", type=int)
    noise_parser.add_argument("--backend")
    noise_parser.add_argument("--device-profile")
    noise_parser.set_defaults(handler=_cmd_noise)

    autotune_parser = subparsers.add_parser("autotune", parents=[common], help="[advanced] probe and cache runtime-only tuning overlays")
    autotune_parser.add_argument("--campaign")
    autotune_parser.add_argument("--lane", choices=["scout", "main", "confirm"])
    autotune_parser.add_argument("--all-lanes", action="store_true")
    autotune_parser.add_argument("--backend")
    autotune_parser.add_argument("--device-profile")
    autotune_parser.add_argument("--force", action="store_true")
    autotune_parser.set_defaults(handler=_cmd_autotune)

    memory_parser = subparsers.add_parser("memory", parents=[common], help="[advanced] memory ingestion and inspection commands")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_backfill = memory_subparsers.add_parser("backfill", parents=[nested_common], help="[advanced] backfill memory records from historical ledger state")
    memory_backfill.add_argument("--campaign", required=True)
    memory_backfill.set_defaults(handler=_cmd_memory_backfill)

    memory_inspect = memory_subparsers.add_parser("inspect", parents=[nested_common], help="[advanced] inspect stored memory records")
    memory_inspect.add_argument("--campaign", required=True)
    memory_inspect.add_argument("--limit", type=int, default=20)
    memory_inspect.set_defaults(handler=_cmd_memory_inspect)

    export_parser = subparsers.add_parser("export-code-proposal", parents=[common], help="[optional code lane] export a code-lane task pack")
    export_parser.add_argument("--proposal-id", required=True)
    export_parser.set_defaults(handler=_cmd_export_code_proposal)

    import_parser = subparsers.add_parser("import-code-proposal", parents=[common], help="[optional code lane] import a returned code-lane patch or worktree")
    import_parser.add_argument("--proposal-id", required=True)
    import_parser.add_argument("--patch-path", type=Path)
    import_parser.add_argument("--worktree-path", type=Path)
    import_parser.set_defaults(handler=_cmd_import_code_proposal)

    smoke = subparsers.add_parser("smoke", parents=[common], help="[advanced] run a quick health check")
    smoke.add_argument("--campaign")
    smoke.add_argument("--gpu", action="store_true", help="include GPU checks")
    smoke.set_defaults(handler=_cmd_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        payload = _with_envelope({}, command=_command_name(args), status="interrupted", message="interrupted")
        _emit(payload, getattr(args, "json", False))
        return EXIT_INTERRUPTED
    except SettingsError as exc:
        payload = _with_envelope(
            {"ok": False, "error": str(exc)},
            command=_command_name(args),
            status="user_error",
            message=str(exc),
        )
        _emit(payload, getattr(args, "json", False))
        return EXIT_USER_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
