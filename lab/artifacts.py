from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .utils import sha256_file, utc_now_iso, write_json

CONTENT_TYPES = {
    ".json": "application/json",
    ".jsonl": "application/jsonl",
    ".log": "text/plain",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".diff": "text/x-diff",
    ".patch": "text/x-diff",
}


def build_artifact_record(
    run_root: Path,
    relative_path: str,
    *,
    kind: str,
    retention_class: str,
    created_at: str | None = None,
) -> dict[str, object]:
    artifact_path = run_root / relative_path
    return {
        "kind": kind,
        "relative_path": relative_path.replace("\\", "/"),
        "sha256": sha256_file(artifact_path) if artifact_path.exists() else None,
        "size_bytes": artifact_path.stat().st_size if artifact_path.exists() else None,
        "retention_class": retention_class,
        "content_type": CONTENT_TYPES.get(artifact_path.suffix.lower(), "application/octet-stream"),
        "created_at": created_at or utc_now_iso(),
    }


def write_artifact_index(run_root: Path, experiment_id: str, artifacts: Iterable[dict[str, object]]) -> dict[str, object]:
    payload = {
        "experiment_id": experiment_id,
        "created_at": utc_now_iso(),
        "artifacts": list(artifacts),
    }
    write_json(run_root / "artifact_index.json", payload)
    return payload
