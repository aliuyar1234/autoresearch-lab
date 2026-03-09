from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIFECYCLE_STATES = (
    "created",
    "preflight_ok",
    "materialized",
    "launching",
    "running",
    "checkpointed",
    "evaluating",
    "completed",
    "failed",
    "discarded",
    "promoted",
    "archived",
)

TERMINAL_STATUSES = ("completed", "failed", "discarded", "promoted")


@dataclass(frozen=True)
class MaterializedRun:
    experiment_id: str
    run_root: Path
    manifest_path: Path
    proposal_path: Path
    config_path: Path
    env_path: Path
    stdout_path: Path
    stderr_path: Path
    summary_path: Path
    artifact_index_path: Path
    checkpoint_path: Path
    checkpoint_meta_path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RunnerResult:
    experiment_id: str
    proposal_id: str | None
    status: str
    crash_class: str | None
    artifact_root: Path
    summary_path: Path
    return_code: int
    primary_metric_value: float
    schema_failed: bool = False
