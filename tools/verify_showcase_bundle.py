from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lab.ledger.db import connect


REQUIRED_ROOT_DOC = "compare.json"
OPTIONAL_DOCS = (
    "candidate_summary.json",
    "validations/validation_summary.json",
)
JSON_REFERENCE_KEYS = {
    "candidate_summary_path",
    "candidate_pool_path",
    "confirm_comparison_path",
    "audit_comparison_path",
    "clean_replays_path",
}
DIRECT_PATH_KEYS = {
    "artifact_root",
    "artifacts_root",
    "archive_snapshot_path",
    "cache_root",
    "candidate_summary_path",
    "clean_replays_path",
    "confirm_comparison_path",
    "audit_comparison_path",
    "candidate_pool_path",
    "db_path",
    "draft_path",
    "leaderboard_snapshot_path",
    "report_root",
    "run_manifest_path",
    "snapshot_manifest_path",
    "summary_path",
    "workspace_root",
    "worktrees_root",
}
PATH_CONTAINER_KEYS = {"artifact_paths", "figure_paths", "report_paths"}
ID_FIELD_TABLES = {
    "campaign_id": ("campaigns", "campaign_id"),
    "experiment_id": ("experiments", "experiment_id"),
    "source_experiment_id": ("experiments", "experiment_id"),
    "replay_experiment_id": ("experiments", "experiment_id"),
    "proposal_id": ("proposals", "proposal_id"),
    "retrieval_event_id": ("retrieval_events", "retrieval_event_id"),
    "review_id": ("validation_reviews", "review_id"),
    "memory_id": ("memory_records", "memory_id"),
}
LIST_ID_FIELD_TABLES = {
    "anchor_experiment_ids": ("experiments", "experiment_id"),
    "candidate_experiment_ids": ("experiments", "experiment_id"),
    "comparator_experiment_ids": ("experiments", "experiment_id"),
    "evidence_memory_ids": ("memory_records", "memory_id"),
    "parent_ids": ("experiments", "experiment_id"),
}


@dataclass(frozen=True)
class RowReference:
    table: str
    column: str
    value: str
    source: str


@dataclass(frozen=True)
class PathReference:
    value: str
    source: str
    expected_kind: str


@dataclass(frozen=True)
class TrustClaim:
    label: str
    experiment_id: str
    review_id: str | None
    source: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify that a published showcase bundle matches stored ledger state.")
    parser.add_argument("--showcase-root", type=Path, required=True)
    parser.add_argument("--db-path", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    showcase_root = args.showcase_root.resolve()
    payload, exit_code = verify_bundle(showcase_root=showcase_root, fallback_db_path=args.db_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return exit_code


def verify_bundle(*, showcase_root: Path, fallback_db_path: Path | None) -> tuple[dict[str, Any], int]:
    loaded_docs: dict[str, dict[str, Any]] = {}
    missing_files: list[dict[str, Any]] = []
    root_compare_path = showcase_root / REQUIRED_ROOT_DOC
    compare_payload = _load_json_doc(root_compare_path, doc_name=REQUIRED_ROOT_DOC, loaded_docs=loaded_docs, missing_files=missing_files)

    for relative_name in OPTIONAL_DOCS:
        path = showcase_root / relative_name
        if path.exists():
            _load_json_doc(path, doc_name=relative_name, loaded_docs=loaded_docs, missing_files=missing_files)

    # Load the JSON artifacts that the main docs explicitly point to.
    discovered_json_refs: list[PathReference] = []
    for doc_name, payload in list(loaded_docs.items()):
        path_refs: list[PathReference] = []
        row_refs: list[RowReference] = []
        trust_claims: list[TrustClaim] = []
        _collect_references(payload, doc_name=doc_name, path="$", parent_key=None, row_refs=row_refs, path_refs=path_refs, trust_claims=trust_claims)
        for ref in path_refs:
            if Path(ref.value).suffix.lower() == ".json" and _last_path_component(ref.source) in JSON_REFERENCE_KEYS:
                discovered_json_refs.append(ref)
    for ref in discovered_json_refs:
        resolved = _resolve_path(showcase_root, ref.value)
        if resolved.exists() and resolved.is_file():
            _load_json_doc(resolved, doc_name=_doc_name_from_path(showcase_root, resolved), loaded_docs=loaded_docs, missing_files=missing_files)

    all_row_refs: list[RowReference] = []
    all_path_refs: list[PathReference] = []
    trust_claims: list[TrustClaim] = []
    for doc_name, payload in loaded_docs.items():
        _collect_references(
            payload,
            doc_name=doc_name,
            path="$",
            parent_key=None,
            row_refs=all_row_refs,
            path_refs=all_path_refs,
            trust_claims=trust_claims,
        )

    db_paths = _discover_db_paths(showcase_root=showcase_root, compare_payload=compare_payload, fallback_db_path=fallback_db_path)
    db_paths = list(dict.fromkeys(db_paths))
    for db_path in db_paths:
        if not db_path.exists():
            missing_files.append(
                {
                    "source": "db-path-discovery",
                    "path": str(db_path),
                    "resolved_path": str(db_path),
                    "expected_kind": "file",
                }
            )

    valid_db_paths = [path for path in db_paths if path.exists()]
    connections = {path: connect(path) for path in valid_db_paths}
    try:
        missing_rows = _find_missing_rows(all_row_refs, connections)
        trust_mismatches = _find_trust_mismatches(trust_claims, connections)
        missing_files.extend(_find_missing_files(showcase_root=showcase_root, refs=all_path_refs))
    finally:
        for connection in connections.values():
            connection.close()

    payload = {
        "ok": not missing_rows and not missing_files and not trust_mismatches and compare_payload is not None,
        "showcase_root": str(showcase_root),
        "db_paths": [str(path) for path in db_paths],
        "checked_counts": {
            "docs": len(loaded_docs),
            "dbs": len(valid_db_paths),
            "row_references": len(all_row_refs),
            "path_references": len(all_path_refs),
            "trust_claims": len(trust_claims),
        },
        "missing_rows": missing_rows,
        "missing_files": missing_files,
        "trust_mismatches": trust_mismatches,
    }
    return payload, 0 if payload["ok"] else 1


def _load_json_doc(
    path: Path,
    *,
    doc_name: str,
    loaded_docs: dict[str, dict[str, Any]],
    missing_files: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not path.exists():
        missing_files.append(
            {
                "source": doc_name,
                "path": str(path),
                "resolved_path": str(path),
                "expected_kind": "file",
            }
        )
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        missing_files.append(
            {
                "source": doc_name,
                "path": str(path),
                "resolved_path": str(path),
                "expected_kind": "json-object",
            }
        )
        return None
    loaded_docs[doc_name] = payload
    return payload


def _collect_references(
    value: Any,
    *,
    doc_name: str,
    path: str,
    parent_key: str | None,
    row_refs: list[RowReference],
    path_refs: list[PathReference],
    trust_claims: list[TrustClaim],
) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("trust_label"), str) and isinstance(value.get("experiment_id"), str):
            trust_claims.append(
                TrustClaim(
                    label=str(value["trust_label"]),
                    experiment_id=str(value["experiment_id"]),
                    review_id=str(value.get("validation_review_id")) if value.get("validation_review_id") else None,
                    source=f"{doc_name}:{path}",
                )
            )
        if isinstance(value.get("replay_experiment_id"), str):
            trust_claims.append(
                TrustClaim(
                    label="replay",
                    experiment_id=str(value["replay_experiment_id"]),
                    review_id=None,
                    source=f"{doc_name}:{path}",
                )
            )
        for key, nested in value.items():
            nested_path = f"{path}.{key}"
            if isinstance(nested, str):
                _append_scalar_reference(
                    nested,
                    key=key,
                    parent_key=parent_key,
                    source=f"{doc_name}:{nested_path}",
                    row_refs=row_refs,
                    path_refs=path_refs,
                )
            elif isinstance(nested, list) and key in LIST_ID_FIELD_TABLES:
                table, column = LIST_ID_FIELD_TABLES[key]
                for index, item in enumerate(nested):
                    if isinstance(item, str) and item:
                        row_refs.append(
                            RowReference(
                                table=table,
                                column=column,
                                value=item,
                                source=f"{doc_name}:{nested_path}[{index}]",
                            )
                        )
            if isinstance(nested, (dict, list)):
                _collect_references(
                    nested,
                    doc_name=doc_name,
                    path=nested_path,
                    parent_key=key,
                    row_refs=row_refs,
                    path_refs=path_refs,
                    trust_claims=trust_claims,
                )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_references(
                item,
                doc_name=doc_name,
                path=f"{path}[{index}]",
                parent_key=parent_key,
                row_refs=row_refs,
                path_refs=path_refs,
                trust_claims=trust_claims,
            )


def _append_scalar_reference(
    value: str,
    *,
    key: str,
    parent_key: str | None,
    source: str,
    row_refs: list[RowReference],
    path_refs: list[PathReference],
) -> None:
    cleaned = value.strip()
    if not cleaned:
        return
    if key in ID_FIELD_TABLES:
        table, column = ID_FIELD_TABLES[key]
        row_refs.append(RowReference(table=table, column=column, value=cleaned, source=source))
    if key in DIRECT_PATH_KEYS or key.endswith("_path") or key.endswith("_root") or parent_key in PATH_CONTAINER_KEYS:
        expected_kind = "dir" if key.endswith("_root") else "file"
        path_refs.append(PathReference(value=cleaned, source=source, expected_kind=expected_kind))


def _discover_db_paths(*, showcase_root: Path, compare_payload: dict[str, Any] | None, fallback_db_path: Path | None) -> list[Path]:
    db_paths: list[Path] = []
    if fallback_db_path is not None:
        db_paths.append(fallback_db_path.resolve())
    if not compare_payload:
        return db_paths
    for pair in compare_payload.get("pairs", []):
        if not isinstance(pair, dict):
            continue
        arms = pair.get("arms", {})
        if not isinstance(arms, dict):
            continue
        for arm in arms.values():
            if not isinstance(arm, dict):
                continue
            db_value = arm.get("db_path")
            if isinstance(db_value, str) and db_value.strip():
                db_paths.append(_resolve_path(showcase_root, db_value))
                continue
            workspace_root = arm.get("workspace_root")
            if isinstance(workspace_root, str) and workspace_root.strip():
                db_paths.append(_resolve_path(showcase_root, workspace_root) / "lab.sqlite3")
    return db_paths


def _find_missing_rows(refs: list[RowReference], connections: dict[Path, sqlite3.Connection]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for ref in refs:
        key = (ref.table, ref.column, ref.value)
        if key in seen:
            continue
        seen.add(key)
        if _row_exists_any(ref=ref, connections=connections):
            continue
        missing.append(
            {
                "table": ref.table,
                "column": ref.column,
                "value": ref.value,
                "source": ref.source,
            }
        )
    return missing


def _row_exists_any(*, ref: RowReference, connections: dict[Path, sqlite3.Connection]) -> bool:
    query = f"SELECT 1 FROM {ref.table} WHERE {ref.column} = ? LIMIT 1"
    for connection in connections.values():
        row = connection.execute(query, (ref.value,)).fetchone()
        if row is not None:
            return True
    return False


def _find_missing_files(*, showcase_root: Path, refs: list[PathReference]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        resolved = _resolve_path(showcase_root, ref.value)
        key = (str(resolved), ref.expected_kind)
        if key in seen:
            continue
        seen.add(key)
        if ref.expected_kind == "dir":
            exists = resolved.exists() and resolved.is_dir()
        else:
            exists = resolved.exists() and resolved.is_file()
        if exists:
            continue
        missing.append(
            {
                "source": ref.source,
                "path": ref.value,
                "resolved_path": str(resolved),
                "expected_kind": ref.expected_kind,
            }
        )
    return missing


def _find_trust_mismatches(claims: list[TrustClaim], connections: dict[Path, sqlite3.Connection]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for claim in claims:
        label = claim.label
        if label in {"confirmed", "audited"}:
            experiment = _experiment_row_any(claim.experiment_id, connections)
            explicit_review_ok = claim.review_id is not None and _validation_review_exists(claim.review_id, connections)
            linked_review_ok = bool(experiment and experiment.get("validation_review_id") and _validation_review_exists(str(experiment["validation_review_id"]), connections))
            source_review_ok = _source_review_exists(claim.experiment_id, connections)
            audited_run_ok = bool(label == "audited" and experiment and str(experiment.get("run_purpose") or "") == "audit")
            if explicit_review_ok or linked_review_ok or source_review_ok or audited_run_ok:
                continue
            mismatches.append(
                {
                    "label": label,
                    "experiment_id": claim.experiment_id,
                    "source": claim.source,
                    "reason": "trust label is not backed by a validation review row or audited experiment state",
                }
            )
        elif label == "replay":
            experiment = _experiment_row_any(claim.experiment_id, connections)
            if experiment and str(experiment.get("run_purpose") or "") == "replay":
                continue
            mismatches.append(
                {
                    "label": label,
                    "experiment_id": claim.experiment_id,
                    "source": claim.source,
                    "reason": "replay artifact is not backed by an experiment row with run_purpose='replay'",
                }
            )
    return mismatches


def _experiment_row_any(experiment_id: str, connections: dict[Path, sqlite3.Connection]) -> dict[str, Any] | None:
    for connection in connections.values():
        row = connection.execute(
            """
            SELECT experiment_id, validation_review_id, validation_state, run_purpose
            FROM experiments
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        ).fetchone()
        if row is not None:
            return dict(row)
    return None


def _validation_review_exists(review_id: str, connections: dict[Path, sqlite3.Connection]) -> bool:
    for connection in connections.values():
        row = connection.execute(
            "SELECT 1 FROM validation_reviews WHERE review_id = ? LIMIT 1",
            (review_id,),
        ).fetchone()
        if row is not None:
            return True
    return False


def _source_review_exists(experiment_id: str, connections: dict[Path, sqlite3.Connection]) -> bool:
    for connection in connections.values():
        row = connection.execute(
            "SELECT 1 FROM validation_reviews WHERE source_experiment_id = ? LIMIT 1",
            (experiment_id,),
        ).fetchone()
        if row is not None:
            return True
    return False


def _resolve_path(showcase_root: Path, raw_value: str) -> Path:
    path = Path(raw_value)
    return path.resolve() if path.is_absolute() else (showcase_root / path).resolve()


def _doc_name_from_path(showcase_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(showcase_root))
    except ValueError:
        return str(path)


def _last_path_component(source: str) -> str:
    _, _, suffix = source.rpartition(".")
    return suffix.split("[", 1)[0]


def _print_human(payload: dict[str, Any]) -> None:
    print(f"ok: {payload['ok']}")
    print(f"showcase_root: {payload['showcase_root']}")
    print(f"checked_counts: {json.dumps(payload['checked_counts'], sort_keys=True)}")
    for key in ("missing_rows", "missing_files", "trust_mismatches"):
        print(f"{key}: {len(payload[key])}")
        for item in payload[key]:
            print(f"  - {json.dumps(item, sort_keys=True)}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
