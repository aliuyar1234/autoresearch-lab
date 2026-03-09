from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from research.dense_gpt.fingerprint import short_fingerprint
from research.dense_gpt.search_space import resolve_dense_config

from ..artifacts import build_artifact_record, write_artifact_index
from ..paths import LabPaths, experiment_root
from ..utils import load_schema, validate_payload, write_json, utc_now_iso
from .contracts import MaterializedRun


def allocate_experiment_id() -> str:
    stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z").replace("T", "_")
    return f"exp_{stamp}_{uuid.uuid4().hex[:8]}"


def _relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _git_commit(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def capture_env() -> dict[str, Any]:
    return {
        "python_executable": os.sys.executable,
        "python_version": os.sys.version.split()[0],
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def materialize_run(
    *,
    paths: LabPaths,
    proposal: dict[str, Any],
    campaign: dict[str, Any],
    run_command: list[str],
    seed: int,
    time_budget_seconds: int,
    device_profile: str,
    backend: str,
    replay_source_experiment_id: str | None = None,
) -> MaterializedRun:
    experiment_id = allocate_experiment_id()
    created_at = utc_now_iso()
    run_root = experiment_root(paths, experiment_id)
    run_root.mkdir(parents=True, exist_ok=True)
    resolved_config = resolve_dense_config(campaign, proposal.get("config_overrides", {}))
    config_fingerprint = str(proposal.get("config_fingerprint") or short_fingerprint(resolved_config))

    manifest = {
        "manifest_id": f"manifest_{experiment_id}",
        "experiment_id": experiment_id,
        "proposal_id": proposal["proposal_id"],
        "campaign_id": campaign["campaign_id"],
        "lane": proposal["lane"],
        "seed": seed,
        "created_at": created_at,
        "working_directory": str(paths.repo_root),
        "run_command": run_command,
        "parent_commit": _git_commit(paths.repo_root),
        "device_profile": device_profile,
        "backend": backend,
        "artifact_root": _relative_or_absolute(run_root, paths.repo_root),
        "time_budget_seconds": int(time_budget_seconds),
        "campaign_version": campaign.get("version"),
        "proposal_family": proposal.get("family"),
        "proposal_kind": proposal.get("kind"),
        "config_fingerprint": config_fingerprint,
        "checkpoint_policy": "pre_eval_if_eligible",
        "pre_eval_checkpoint_path": _relative_or_absolute(run_root / "checkpoints" / "pre_eval.safetensors", paths.repo_root),
        "pre_eval_meta_path": _relative_or_absolute(run_root / "checkpoints" / "pre_eval.meta.json", paths.repo_root),
        "summary_target_path": _relative_or_absolute(run_root / "summary.json", paths.repo_root),
        "env_capture": capture_env(),
    }
    if replay_source_experiment_id is not None:
        manifest["replay_source_experiment_id"] = replay_source_experiment_id

    validate_payload(manifest, load_schema(paths.schemas_root / "run_manifest.schema.json"))

    manifest_path = run_root / "manifest.json"
    proposal_path = run_root / "proposal.json"
    config_path = run_root / "config.json"
    env_path = run_root / "env.json"
    stdout_path = run_root / "stdout.log"
    stderr_path = run_root / "stderr.log"
    summary_path = run_root / "summary.json"
    artifact_index_path = run_root / "artifact_index.json"
    checkpoint_dir = run_root / "checkpoints"
    checkpoint_path = checkpoint_dir / "pre_eval.safetensors"
    checkpoint_meta_path = checkpoint_dir / "pre_eval.meta.json"

    write_json(manifest_path, manifest)
    write_json(proposal_path, proposal)
    write_json(config_path, resolved_config)
    write_json(env_path, manifest["env_capture"])
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")

    artifact_records = [
        build_artifact_record(run_root, "manifest.json", kind="manifest", retention_class="full", created_at=created_at),
        build_artifact_record(run_root, "proposal.json", kind="proposal", retention_class="full", created_at=created_at),
        build_artifact_record(run_root, "config.json", kind="config", retention_class="full", created_at=created_at),
        build_artifact_record(run_root, "env.json", kind="env", retention_class="full", created_at=created_at),
        build_artifact_record(run_root, "stdout.log", kind="stdout", retention_class="discardable", created_at=created_at),
        build_artifact_record(run_root, "stderr.log", kind="stderr", retention_class="discardable", created_at=created_at),
    ]
    artifact_index = write_artifact_index(run_root, experiment_id, artifact_records)
    validate_payload(artifact_index, load_schema(paths.schemas_root / "artifact_index.schema.json"))

    return MaterializedRun(
        experiment_id=experiment_id,
        run_root=run_root,
        manifest_path=manifest_path,
        proposal_path=proposal_path,
        config_path=config_path,
        env_path=env_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        summary_path=summary_path,
        artifact_index_path=artifact_index_path,
        checkpoint_path=checkpoint_path,
        checkpoint_meta_path=checkpoint_meta_path,
        manifest=manifest,
    )
