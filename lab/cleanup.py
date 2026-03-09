from __future__ import annotations

from pathlib import Path
from typing import Any

from .ledger.queries import delete_artifact_rows, list_artifact_rows
from .utils import load_schema, utc_now_iso, validate_payload, write_json
from .utils.fs import is_within

PRUNEABLE_RETENTION_CLASSES = {"discardable", "ephemeral"}


def select_cleanup_candidates(rows: list[dict[str, Any]], *, artifacts_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row in rows:
        artifact_path = Path(str(row["artifact_root"])) / str(row["relative_path"])
        payload = {
            "artifact_id": int(row["id"]),
            "experiment_id": str(row["experiment_id"]),
            "kind": str(row["kind"]),
            "retention_class": str(row["retention_class"]),
            "path": str(artifact_path),
            "size_bytes": int(row["size_bytes"] or 0),
            "exists": artifact_path.exists(),
        }
        if str(row["retention_class"]) not in PRUNEABLE_RETENTION_CLASSES:
            skipped.append({**payload, "reason": "retained"})
            continue
        if not is_within(artifact_path, artifacts_root):
            skipped.append({**payload, "reason": "outside_managed_root"})
            continue
        candidates.append(payload)
    return candidates, skipped


def run_cleanup(connection, *, paths, apply: bool, campaign_id: str | None = None) -> dict[str, Any]:
    rows = list_artifact_rows(
        connection,
        retention_classes=sorted(PRUNEABLE_RETENTION_CLASSES),
        campaign_id=campaign_id,
    )
    candidates, skipped = select_cleanup_candidates(rows, artifacts_root=paths.artifacts_root)
    reclaimed_bytes = 0
    deleted_paths: list[str] = []
    deleted_ids: list[int] = []
    touched_experiments: set[str] = set()
    missing_candidates = 0

    if apply:
        for candidate in candidates:
            artifact_path = Path(candidate["path"])
            if artifact_path.exists():
                reclaimed_bytes += int(candidate["size_bytes"])
                artifact_path.unlink()
                deleted_paths.append(str(artifact_path))
                _prune_empty_parents(artifact_path.parent, stop=paths.artifacts_root)
            else:
                missing_candidates += 1
            deleted_ids.append(int(candidate["artifact_id"]))
            touched_experiments.add(str(candidate["experiment_id"]))

        delete_artifact_rows(connection, deleted_ids)
        for experiment_id in sorted(touched_experiments):
            _refresh_artifact_index(connection, paths=paths, experiment_id=experiment_id)

    payload = {
        "ok": True,
        "campaign_id": campaign_id,
        "apply": apply,
        "dry_run": not apply,
        "candidate_count": len(candidates),
        "deleted_count": len(deleted_ids) if apply else 0,
        "missing_candidate_count": missing_candidates if apply else sum(1 for item in candidates if not item["exists"]),
        "reclaimed_bytes": reclaimed_bytes,
        "skipped_count": len(skipped),
        "candidates": candidates,
        "skipped": skipped,
        "deleted_paths": deleted_paths,
    }
    return payload


def _refresh_artifact_index(connection, *, paths, experiment_id: str) -> None:
    rows = list_artifact_rows(connection, experiment_id=experiment_id)
    if not rows:
        return
    run_root = Path(str(rows[0]["artifact_root"]))
    if not run_root.exists():
        return
    artifact_index = {
        "experiment_id": experiment_id,
        "created_at": utc_now_iso(),
        "artifacts": [
            {
                "kind": str(row["kind"]),
                "relative_path": str(row["relative_path"]),
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "retention_class": str(row["retention_class"]),
                "content_type": str(row["content_type"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ],
    }
    validate_payload(artifact_index, load_schema(paths.schemas_root / "artifact_index.schema.json"))
    write_json(run_root / "artifact_index.json", artifact_index)


def _prune_empty_parents(path: Path, *, stop: Path) -> None:
    current = path
    stop_resolved = stop.resolve()
    while current.exists() and current.resolve() != stop_resolved:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


__all__ = ["PRUNEABLE_RETENTION_CLASSES", "run_cleanup", "select_cleanup_candidates"]
