from __future__ import annotations

from typing import Any

from ..idea_signatures import compute_idea_signature, scientific_mutation_paths


def exhaustion_summary(experiments: list[dict[str, Any]], *, campaign_id: str) -> dict[str, dict[str, int | bool]]:
    by_signature: dict[str, dict[str, int | bool]] = {}
    for row in experiments:
        if str(row.get("campaign_id")) != campaign_id:
            continue
        signature = str(row.get("idea_signature") or "")
        if not signature:
            continue
        stats = by_signature.setdefault(
            signature,
            {
                "attempt_count": 0,
                "failed_count": 0,
                "discarded_count": 0,
                "validation_failed_count": 0,
                "promoted_count": 0,
                "archived_count": 0,
                "pending_validation_count": 0,
                "harmful_score": 0,
                "helpful_score": 0,
                "exhausted": False,
            },
        )
        stats["attempt_count"] = int(stats["attempt_count"]) + 1
        disposition = str(row.get("disposition") or "")
        if str(row.get("status")) != "completed":
            stats["failed_count"] = int(stats["failed_count"]) + 1
        if disposition == "discarded":
            stats["discarded_count"] = int(stats["discarded_count"]) + 1
        if str(row.get("validation_state") or "") == "failed":
            stats["validation_failed_count"] = int(stats["validation_failed_count"]) + 1
        if disposition == "promoted":
            stats["promoted_count"] = int(stats["promoted_count"]) + 1
        if disposition == "archived":
            stats["archived_count"] = int(stats["archived_count"]) + 1
        if disposition == "pending_validation":
            stats["pending_validation_count"] = int(stats["pending_validation_count"]) + 1

    for stats in by_signature.values():
        harmful_score = (
            2 * int(stats["failed_count"])
            + int(stats["discarded_count"])
            + int(stats["validation_failed_count"])
        )
        helpful_score = (
            3 * int(stats["promoted_count"])
            + int(stats["archived_count"])
            + int(stats["pending_validation_count"])
        )
        stats["harmful_score"] = harmful_score
        stats["helpful_score"] = helpful_score
        stats["exhausted"] = (
            int(stats["attempt_count"]) >= 2
            and helpful_score == 0
            and harmful_score - helpful_score >= 3
        )
    return by_signature


def is_exhausted_signature(signature: str | None, *, experiments: list[dict[str, Any]], campaign_id: str) -> bool:
    if not signature:
        return False
    stats = exhaustion_summary(experiments, campaign_id=campaign_id).get(signature)
    return bool(stats and stats["exhausted"])
