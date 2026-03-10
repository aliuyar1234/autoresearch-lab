from __future__ import annotations

from typing import Any


def preferred_record_types(*, family: str, lane: str) -> tuple[str, ...]:
    mapping = {
        "baseline": ("champion_snapshot", "experiment_result"),
        "exploit": ("champion_snapshot", "experiment_result", "validation_review"),
        "ablation": ("failure_autopsy", "validation_review", "experiment_result"),
        "combine": ("champion_snapshot", "validation_review"),
        "novel": ("failure_autopsy", "report_note", "experiment_result"),
        "manual": ("report_note", "champion_snapshot", "experiment_result"),
    }
    return mapping.get(family, ("experiment_result",))


def role_for_record(*, family: str, record: dict[str, Any]) -> str:
    record_type = str(record.get("record_type") or "")
    outcome_label = str(record.get("outcome_label") or "")
    if record_type == "report_note":
        return "report_note"
    if record_type == "failure_autopsy" or outcome_label in {"failed", "discarded"}:
        return "warning"
    if family == "combine" and outcome_label in {"promoted", "passed", "archived", "pending_validation"}:
        return "combination_parent"
    return "supporting_precedent"


def is_warning_record(record: dict[str, Any]) -> bool:
    return role_for_record(family="novel", record=record) == "warning"


def is_positive_record(record: dict[str, Any]) -> bool:
    return str(record.get("record_type") or "") == "champion_snapshot" or str(record.get("outcome_label") or "") in {
        "promoted",
        "passed",
        "archived",
        "pending_validation",
    }


def are_mergeable_parent_records(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_payload = left.get("payload") if isinstance(left.get("payload"), dict) else {}
    right_payload = right.get("payload") if isinstance(right.get("payload"), dict) else {}
    left_overrides = left_payload.get("config_overrides") if isinstance(left_payload.get("config_overrides"), dict) else {}
    right_overrides = right_payload.get("config_overrides") if isinstance(right_payload.get("config_overrides"), dict) else {}
    if not left_overrides or not right_overrides:
        return False
    return disjoint_mergeable(left_overrides, right_overrides)


def disjoint_mergeable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_paths = {path for path, _ in _flatten_override_paths(left)}
    right_paths = {path for path, _ in _flatten_override_paths(right)}
    return left_paths.isdisjoint(right_paths)


def _flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in sorted(payload.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(_flatten_override_paths(value, path))
        else:
            items.append((path, value))
    return items
