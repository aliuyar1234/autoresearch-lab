from __future__ import annotations

from typing import Any


RANKABLE_RUN_PURPOSES = {"search", "baseline"}


def normalize_run_purpose(row: dict[str, Any]) -> str:
    return str(row.get("run_purpose") or "search")


def normalize_validation_state(row: dict[str, Any]) -> str:
    return str(row.get("validation_state") or "not_required")


def normalize_eval_split(row: dict[str, Any]) -> str:
    return str(row.get("eval_split") or "search_val")


def is_rankable_experiment(row: dict[str, Any]) -> bool:
    return normalize_run_purpose(row) in RANKABLE_RUN_PURPOSES


def is_completed_metric_run(row: dict[str, Any]) -> bool:
    return str(row.get("status") or "completed") == "completed" and row.get("primary_metric_value") is not None


def is_validated_promotion(row: dict[str, Any]) -> bool:
    if str(row.get("disposition")) != "promoted":
        return False
    if not is_rankable_experiment(row):
        return False
    if str(row.get("lane")) != "confirm":
        return True
    return normalize_validation_state(row) in {"passed", "not_required"}


def is_pending_validation(row: dict[str, Any]) -> bool:
    return str(row.get("disposition")) == "pending_validation" and normalize_validation_state(row) == "pending"
