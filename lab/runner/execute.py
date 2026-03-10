from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..artifacts import build_artifact_record, write_artifact_index
from ..backends import (
    apply_runtime_autotune_metadata,
    available_backend_candidates,
    backend_blacklist_path,
    backend_cache_path,
    detect_device_profile,
    ensure_cuda_path_configured,
    record_backend_failure,
    resolve_runtime_autotune,
    select_backend,
    shape_family_for_run,
)
from ..code_proposals import CodeProposalImportError, prepare_code_patch_execution
from ..ledger.db import apply_migrations, connect
from ..ledger.queries import (
    list_campaign_experiments,
    list_prior_experiments,
    replace_artifacts,
    replace_campaign_archive_rows,
    set_proposal_status,
    upsert_campaign,
    upsert_experiment,
    upsert_proposal,
)
from ..memory import ingest_experiment_memory, persist_proposal_memory_state
from ..paths import LabPaths
from ..proposals import normalize_proposal_payload
from ..scoring import best_baseline, explain_experiment_score
from ..scheduler import archive_rows_from_snapshot, build_archive_snapshot, write_archive_snapshot
from ..utils import SchemaValidationError, load_schema, read_json, utc_now_iso, validate_payload, write_json
from research.dense_gpt.fingerprint import short_fingerprint
from research.dense_gpt.search_space import resolve_dense_config
from .contracts import RunnerResult
from .failures import classify_failure
from .materialize import materialize_run

EXIT_TIMEOUT_RETURN_CODE = 124


def _render_command(template: list[str], values: dict[str, str]) -> list[str]:
    return [part.format(**values) for part in template]


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


def _select_backend_for_config(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    resolved_config: dict[str, Any],
    detected_profile,
) -> tuple[str, Any, Any]:
    shape_family = shape_family_for_run(campaign, resolved_config, detected_profile, purpose="train")
    torch_version, cuda_version = _torch_runtime_versions()
    backend_selection = select_backend(
        cache_path=backend_cache_path(paths),
        blacklist_path=backend_blacklist_path(paths),
        candidates=available_backend_candidates(detected_profile),
        shape=shape_family,
        device_profile=detected_profile,
        cuda_version=cuda_version,
        torch_version=torch_version,
        compile_enabled=bool(resolved_config["runtime"].get("compile_enabled", True)),
    )
    return backend_selection.backend, backend_selection, shape_family


def _apply_runtime_summary_metadata(summary: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    payload = dict(summary)
    payload.setdefault("runtime_defaults", manifest.get("runtime_defaults"))
    payload.setdefault("runtime_overlay", manifest.get("runtime_overlay"))
    payload.setdefault("runtime_effective", manifest.get("runtime_effective"))
    payload.setdefault("autotune", manifest.get("autotune"))
    return payload


def _summary_defaults(manifest: dict[str, Any], proposal: dict[str, Any], campaign: dict[str, Any], *, status: str, crash_class: str | None) -> dict[str, Any]:
    return {
        "experiment_id": manifest["experiment_id"],
        "proposal_id": manifest.get("proposal_id"),
        "campaign_id": manifest["campaign_id"],
        "lane": manifest["lane"],
        "status": status,
        "eval_split": manifest.get("eval_split", "search_val"),
        "run_purpose": manifest.get("run_purpose", "search"),
        "replay_source_experiment_id": manifest.get("replay_source_experiment_id"),
        "validation_state": "not_required",
        "validation_review_id": manifest.get("validation_review_id"),
        "idea_signature": proposal.get("idea_signature"),
        "disposition": None,
        "crash_class": crash_class,
        "proposal_family": proposal.get("family"),
        "proposal_kind": proposal.get("kind"),
        "complexity_cost": proposal.get("complexity_cost"),
        "primary_metric_name": campaign["primary_metric"]["name"],
        "primary_metric_value": 0.0,
        "metric_delta": None,
        "budget_seconds": manifest["time_budget_seconds"],
        "train_seconds": 0.0,
        "eval_seconds": 0.0,
        "compile_seconds": 0.0,
        "tokens_processed": 0,
        "tokens_per_second": 0.0,
        "steady_state_mfu": None,
        "peak_vram_gb": 0.0,
        "param_count": None,
        "backend": manifest["backend"],
        "device_profile": manifest["device_profile"],
        "seed": manifest["seed"],
        "config_fingerprint": manifest.get("config_fingerprint") or "unknown",
        "git_commit": manifest["parent_commit"],
        "warnings": [],
        "checkpoint_path": None,
        "summary_version": "1.0.0",
        "started_at": manifest["created_at"],
        "ended_at": utc_now_iso(),
        "runtime_defaults": manifest.get("runtime_defaults"),
        "runtime_overlay": manifest.get("runtime_overlay"),
        "runtime_effective": manifest.get("runtime_effective"),
        "autotune": manifest.get("autotune"),
    }


def _synthesize_failure_summary(
    manifest: dict[str, Any],
    proposal: dict[str, Any],
    campaign: dict[str, Any],
    *,
    crash_class: str,
    warning: str,
) -> dict[str, Any]:
    payload = _summary_defaults(manifest, proposal, campaign, status="failed", crash_class=crash_class)
    payload["warnings"] = [warning]
    return payload


def _load_or_synthesize_summary(
    *,
    summary_path: Path,
    manifest: dict[str, Any],
    proposal: dict[str, Any],
    campaign: dict[str, Any],
    crash_class: str | None,
    warning: str | None = None,
) -> dict[str, Any]:
    if summary_path.exists():
        payload = read_json(summary_path)
        payload.setdefault("proposal_family", proposal.get("family"))
        payload.setdefault("proposal_kind", proposal.get("kind"))
        payload.setdefault("complexity_cost", proposal.get("complexity_cost"))
        payload.setdefault("eval_split", manifest.get("eval_split", "search_val"))
        payload.setdefault("run_purpose", manifest.get("run_purpose", "search"))
        payload.setdefault("replay_source_experiment_id", manifest.get("replay_source_experiment_id"))
        payload.setdefault("validation_state", "not_required")
        payload.setdefault("validation_review_id", manifest.get("validation_review_id"))
        payload.setdefault("idea_signature", proposal.get("idea_signature"))
        payload.setdefault("primary_metric_name", campaign["primary_metric"]["name"])
        payload.setdefault("git_commit", manifest["parent_commit"])
        payload.setdefault("backend", manifest["backend"])
        payload.setdefault("device_profile", manifest["device_profile"])
        payload.setdefault("seed", manifest["seed"])
        payload.setdefault("config_fingerprint", manifest.get("config_fingerprint") or "unknown")
        payload.setdefault("warnings", [])
        payload.setdefault("summary_version", "1.0.0")
        payload.setdefault("started_at", manifest["created_at"])
        payload.setdefault("ended_at", utc_now_iso())
        payload.setdefault("runtime_defaults", manifest.get("runtime_defaults"))
        payload.setdefault("runtime_overlay", manifest.get("runtime_overlay"))
        payload.setdefault("runtime_effective", manifest.get("runtime_effective"))
        payload.setdefault("autotune", manifest.get("autotune"))
        return payload
    return _apply_runtime_summary_metadata(_synthesize_failure_summary(
        manifest,
        proposal,
        campaign,
        crash_class=crash_class or "unknown",
        warning=warning or "summary.json missing; runner synthesized failure record",
    ), manifest)


def execute_experiment(
    *,
    paths: LabPaths,
    proposal: dict[str, Any],
    campaign: dict[str, Any],
    target_command_template: list[str],
    seed: int,
    time_budget_seconds: int,
    device_profile: str | None = None,
    backend: str | None = None,
    eval_split: str = "search_val",
    run_purpose: str = "search",
    validation_review_id: str | None = None,
    replay_source_experiment_id: str | None = None,
    score_result: bool = True,
) -> RunnerResult:
    proposal = normalize_proposal_payload(proposal)
    configured_cuda_path = ensure_cuda_path_configured()
    detected_profile = detect_device_profile(device_profile)
    resolved_config = resolve_dense_config(campaign, proposal.get("config_overrides", {}), device_profile=detected_profile)
    scientific_config_fingerprint = str(proposal.get("config_fingerprint") or short_fingerprint(resolved_config))
    backend_selection = None
    shape_family = shape_family_for_run(campaign, resolved_config, detected_profile, purpose="train")

    if backend is None:
        backend, backend_selection, shape_family = _select_backend_for_config(
            paths=paths,
            campaign=campaign,
            resolved_config=resolved_config,
            detected_profile=detected_profile,
        )
    device_profile = detected_profile.profile_id
    runtime_autotune = resolve_runtime_autotune(
        paths,
        campaign=campaign,
        lane=str(proposal["lane"]),
        device_profile=detected_profile,
        backend=str(backend),
        resolved_config=resolved_config,
    )
    resolved_config = apply_runtime_autotune_metadata(resolved_config, runtime_autotune)

    validate_payload(proposal, load_schema(paths.schemas_root / "proposal.schema.json"))

    materialized = materialize_run(
        paths=paths,
        proposal=proposal,
        campaign=campaign,
        run_command=target_command_template,
        seed=seed,
        time_budget_seconds=time_budget_seconds,
        device_profile=device_profile,
        backend=backend,
        eval_split=eval_split,
        run_purpose=run_purpose,
        validation_review_id=validation_review_id,
        replay_source_experiment_id=replay_source_experiment_id,
        resolved_config=resolved_config,
        config_fingerprint=scientific_config_fingerprint,
    )

    apply_migrations(paths.db_path, paths.sql_root)
    connection = connect(paths.db_path)
    started_at = utc_now_iso()
    upsert_campaign(connection, campaign, timestamp=started_at)
    upsert_proposal(connection, proposal, updated_at=started_at)
    persist_proposal_memory_state(connection, paths=paths, proposal=proposal)
    set_proposal_status(connection, proposal["proposal_id"], "running", updated_at=started_at)
    connection.commit()

    template_values = {
        "summary_out": str(materialized.summary_path),
        "config_path": str(materialized.config_path),
        "experiment_id": materialized.experiment_id,
        "proposal_id": proposal["proposal_id"],
        "campaign_id": proposal["campaign_id"],
        "lane": proposal["lane"],
        "eval_split": eval_split,
        "run_purpose": run_purpose,
        "validation_review_id": validation_review_id or "",
        "backend": backend,
        "device_profile": device_profile,
        "repo_root": str(paths.repo_root),
        "artifacts_root": str(paths.artifacts_root),
        "cache_root": str(paths.cache_root),
        "time_budget_seconds": str(time_budget_seconds),
        "seed": str(seed),
    }

    stdout_text = ""
    stderr_text = ""
    return_code = 0
    crash_class: str | None = None

    try:
        execution_root = paths.repo_root
        code_patch_execution = None
        if proposal.get("kind") == "code_patch":
            code_patch_execution = prepare_code_patch_execution(paths, proposal, experiment_id=materialized.experiment_id)
            if code_patch_execution is not None:
                execution_root = code_patch_execution["execution_root"]

        command = _render_command(target_command_template, {**template_values, "repo_root": str(execution_root)})
        materialized.manifest["run_command"] = command
        materialized.manifest["working_directory"] = str(execution_root)
        write_json(materialized.manifest_path, materialized.manifest)

        env = dict(os.environ)
        env.update(
            {
                "LAB_SUMMARY_OUT": str(materialized.summary_path),
                "LAB_EXPERIMENT_ID": materialized.experiment_id,
                "LAB_PROPOSAL_ID": proposal["proposal_id"],
                "LAB_CAMPAIGN_ID": proposal["campaign_id"],
                "LAB_LANE": proposal["lane"],
                "LAB_EVAL_SPLIT": eval_split,
                "LAB_RUN_PURPOSE": run_purpose,
                "LAB_BACKEND": backend,
                "LAB_DEVICE_PROFILE": device_profile,
                "LAB_REPO_ROOT": str(execution_root),
                "LAB_EXECUTION_REPO_ROOT": str(execution_root),
                "LAB_ARTIFACTS_ROOT": str(paths.artifacts_root),
                "LAB_CACHE_ROOT": str(paths.cache_root),
                "LAB_CONFIG_PATH": str(materialized.config_path),
                "LAB_CONFIG_FINGERPRINT": str(materialized.manifest.get("config_fingerprint") or scientific_config_fingerprint),
                "LAB_CAMPAIGN_MANIFEST_PATH": str(paths.campaigns_root / proposal["campaign_id"] / "campaign.json"),
                "LAB_ARTIFACT_ROOT": str(materialized.run_root),
                "LAB_PARENT_COMMIT": materialized.manifest["parent_commit"],
                "LAB_TIME_BUDGET_SECONDS": str(time_budget_seconds),
                "LAB_PRE_EVAL_CHECKPOINT_PATH": str(materialized.checkpoint_path),
                "LAB_PRE_EVAL_META_PATH": str(materialized.checkpoint_meta_path),
            }
        )
        if configured_cuda_path and "CUDA_PATH" not in env:
            env["CUDA_PATH"] = configured_cuda_path
        if replay_source_experiment_id is not None:
            env["LAB_REPLAY_SOURCE_EXPERIMENT_ID"] = replay_source_experiment_id
        if validation_review_id is not None:
            env["LAB_VALIDATION_REVIEW_ID"] = validation_review_id
        if code_patch_execution is not None:
            env["LAB_CODE_IMPORT_ROOT"] = str(code_patch_execution["import_root"])
            env["LAB_CODE_CHANGED_FILES"] = json.dumps(code_patch_execution["return_manifest"].get("changed_files", []))
            env["LAB_CODE_DELETED_FILES"] = json.dumps(code_patch_execution["return_manifest"].get("deleted_files", []))
            env["LAB_CODE_RETURN_KIND"] = str(code_patch_execution["return_manifest"].get("return_kind") or "unknown")

        completed = subprocess.run(
            command,
            cwd=execution_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=time_budget_seconds,
            check=False,
        )
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        return_code = completed.returncode
        if completed.returncode != 0:
            crash_class = classify_failure(stderr_text=stderr_text, stdout_text=stdout_text).crash_class
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout or ""
        stderr_text = (exc.stderr or "") + "\nrunner timeout"
        return_code = EXIT_TIMEOUT_RETURN_CODE
        crash_class = "timeout"
    except CodeProposalImportError as exc:
        stdout_text = ""
        stderr_text = str(exc)
        return_code = 91
        crash_class = "assertion_failure"

    materialized.stdout_path.write_text(stdout_text, encoding="utf-8")
    materialized.stderr_path.write_text(stderr_text, encoding="utf-8")

    if return_code == 0:
        summary = _load_or_synthesize_summary(
            summary_path=materialized.summary_path,
            manifest=materialized.manifest,
            proposal=proposal,
            campaign=campaign,
            crash_class=None,
        )
    else:
        summary = _load_or_synthesize_summary(
            summary_path=materialized.summary_path,
            manifest=materialized.manifest,
            proposal=proposal,
            campaign=campaign,
            crash_class=crash_class or "unknown",
            warning=f"target exited with return code {return_code}",
        )
        summary["status"] = "failed"
        summary["crash_class"] = crash_class or "unknown"
        if backend_selection is not None and summary["crash_class"] in {"backend_unavailable", "compile_error", "oom_train", "oom_eval"}:
            record_backend_failure(
                paths,
                backend=backend,
                shape_family=shape_family.family_id,
                reason=str(summary["crash_class"]),
            )
    summary = _apply_runtime_summary_metadata(summary, materialized.manifest)

    if materialized.checkpoint_path.exists():
        summary["checkpoint_path"] = str(materialized.checkpoint_path)
    if materialized.checkpoint_meta_path.exists():
        summary.setdefault("warnings", [])

    if score_result and _summary_is_scoreable(summary):
        prior_experiments = list_prior_experiments(
            connection,
            str(summary["campaign_id"]),
            str(summary["lane"]),
            exclude_experiment_id=materialized.experiment_id,
        )
        baseline = best_baseline(prior_experiments, direction=str(campaign["primary_metric"]["direction"]))
        score = explain_experiment_score(experiment=summary, campaign=campaign, baseline=baseline)
        summary["disposition"] = score.final_disposition
        summary["metric_delta"] = score.metric_delta
        summary["score_reason"] = score.reason
        summary["score_archive_effect"] = score.archive_effect
        summary["score_baseline_experiment_id"] = score.baseline_experiment_id
        summary["validation_state"] = score.validation_state

    write_json(materialized.summary_path, summary)

    run_artifacts = [
        build_artifact_record(materialized.run_root, "manifest.json", kind="manifest", retention_class="full"),
        build_artifact_record(materialized.run_root, "proposal.json", kind="proposal", retention_class="full"),
        build_artifact_record(materialized.run_root, "config.json", kind="config", retention_class="full"),
        build_artifact_record(materialized.run_root, "env.json", kind="env", retention_class="full"),
        build_artifact_record(
            materialized.run_root,
            "stdout.log",
            kind="stdout",
            retention_class="crash_exemplar" if summary["status"] == "failed" else "discardable",
        ),
        build_artifact_record(
            materialized.run_root,
            "stderr.log",
            kind="stderr",
            retention_class="crash_exemplar" if summary["status"] == "failed" else "discardable",
        ),
        build_artifact_record(
            materialized.run_root,
            "summary.json",
            kind="summary",
            retention_class="full" if summary["status"] == "completed" else "crash_exemplar",
        ),
    ]
    run_artifacts.extend(_checkpoint_artifacts(materialized, summary))
    artifact_index = write_artifact_index(materialized.run_root, materialized.experiment_id, run_artifacts)
    schema_failed = False

    try:
        validate_payload(summary, load_schema(paths.schemas_root / "experiment_record.schema.json"))
        validate_payload(artifact_index, load_schema(paths.schemas_root / "artifact_index.schema.json"))
    except SchemaValidationError as exc:
        schema_failed = True
        crash_class = crash_class or "unknown"
        summary = _apply_runtime_summary_metadata(_synthesize_failure_summary(
            materialized.manifest,
            proposal,
            campaign,
            crash_class=crash_class,
            warning=f"schema validation failed: {exc}",
        ), materialized.manifest)
        write_json(materialized.summary_path, summary)
        run_artifacts = [
            build_artifact_record(materialized.run_root, "manifest.json", kind="manifest", retention_class="full"),
            build_artifact_record(materialized.run_root, "proposal.json", kind="proposal", retention_class="full"),
            build_artifact_record(materialized.run_root, "config.json", kind="config", retention_class="full"),
            build_artifact_record(materialized.run_root, "env.json", kind="env", retention_class="full"),
            build_artifact_record(materialized.run_root, "stdout.log", kind="stdout", retention_class="crash_exemplar"),
            build_artifact_record(materialized.run_root, "stderr.log", kind="stderr", retention_class="crash_exemplar"),
            build_artifact_record(materialized.run_root, "summary.json", kind="summary", retention_class="crash_exemplar"),
        ]
        run_artifacts.extend(_checkpoint_artifacts(materialized, summary))
        artifact_index = write_artifact_index(materialized.run_root, materialized.experiment_id, run_artifacts)

    ended_at = summary.get("ended_at") or utc_now_iso()
    upsert_experiment(
        connection,
        summary,
        artifact_root=materialized.run_root,
        crash_class=summary.get("crash_class"),
        disposition=summary.get("disposition"),
    )
    experiment_row = next(
        (
            row
            for row in list_campaign_experiments(connection, str(summary["campaign_id"]))
            if str(row["experiment_id"]) == str(materialized.experiment_id)
        ),
        None,
    )
    if experiment_row is not None:
        ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment_row)
    replace_artifacts(connection, artifact_index)
    campaign_snapshot = build_archive_snapshot(list_campaign_experiments(connection, str(summary["campaign_id"])))
    replace_campaign_archive_rows(
        connection,
        str(summary["campaign_id"]),
        archive_rows_from_snapshot(str(summary["campaign_id"]), campaign_snapshot, created_at=ended_at),
    )
    write_archive_snapshot(paths, str(summary["campaign_id"]), campaign_snapshot)
    set_proposal_status(
        connection,
        proposal["proposal_id"],
        _proposal_terminal_status(summary),
        updated_at=ended_at,
    )
    connection.commit()
    connection.close()

    return RunnerResult(
        experiment_id=materialized.experiment_id,
        proposal_id=proposal["proposal_id"],
        status=summary["status"],
        crash_class=summary.get("crash_class"),
        artifact_root=materialized.run_root,
        summary_path=materialized.summary_path,
        return_code=return_code,
        primary_metric_value=float(summary["primary_metric_value"]),
        schema_failed=schema_failed,
    )


def _checkpoint_artifacts(materialized, summary: dict[str, Any]) -> list[dict[str, object]]:
    retention_class = "discardable"
    if summary["status"] != "completed":
        retention_class = "crash_exemplar"
    elif summary.get("disposition") in {"promoted", "archived"}:
        retention_class = "promoted"

    artifacts: list[dict[str, object]] = []
    if materialized.checkpoint_path.exists():
        artifacts.append(
            build_artifact_record(
                materialized.run_root,
                "checkpoints/pre_eval.safetensors",
                kind="checkpoint",
                retention_class=retention_class,
            )
        )
    if materialized.checkpoint_meta_path.exists():
        artifacts.append(
            build_artifact_record(
                materialized.run_root,
                "checkpoints/pre_eval.meta.json",
                kind="checkpoint",
                retention_class=retention_class,
            )
        )
    return artifacts


def _proposal_terminal_status(summary: dict[str, Any]) -> str:
    if summary["status"] != "completed":
        return "discarded"
    disposition = summary.get("disposition")
    if disposition in {"promoted", "archived", "discarded"}:
        return str(disposition)
    return "completed"


def _summary_is_scoreable(summary: dict[str, Any]) -> bool:
    required_keys = {
        "experiment_id",
        "campaign_id",
        "lane",
        "status",
        "primary_metric_value",
        "complexity_cost",
    }
    return required_keys.issubset(summary)
