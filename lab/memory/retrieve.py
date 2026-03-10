from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..utils import utc_now_iso
from .models import retrieval_event_id_for
from .selectors import are_mergeable_parent_records, is_positive_record, is_warning_record, preferred_record_types, role_for_record


def retrieve_memory_context(
    *,
    memory_records: list[dict[str, Any]],
    campaign_id: str,
    comparability_group: str,
    proposal_id: str,
    family: str,
    lane: str,
    tags: list[str],
    query_payload: dict[str, Any],
    query_text: str,
) -> dict[str, Any]:
    normalized_tags = sorted({str(tag) for tag in tags if tag})
    preferred_types = preferred_record_types(family=family, lane=lane)
    scored = []
    for record in memory_records:
        score, reasons = _score_record(
            record,
            campaign_id=campaign_id,
            comparability_group=comparability_group,
            family=family,
            lane=lane,
            tags=normalized_tags,
            preferred_types=preferred_types,
        )
        if score <= 0:
            continue
        scored.append(
            {
                **record,
                "score": round(score, 6),
                "score_reason": "; ".join(reasons),
                "role_hint": role_for_record(family=family, record=record),
            }
        )

    scored.sort(key=lambda item: (-float(item["score"]), str(item.get("updated_at") or ""), str(item["memory_id"])))
    preliminary = scored[:12]
    selected = _select_citations(family=family, preliminary=preliminary)
    selected_ids = {item["memory_id"] for item in selected}
    items = [
        {
            "memory_id": item["memory_id"],
            "rank": index,
            "score": float(item["score"]),
            "selected_for_context": item["memory_id"] in selected_ids,
            "role_hint": item["role_hint"],
            "reason": item["score_reason"],
        }
        for index, item in enumerate(preliminary, start=1)
    ]
    evidence = [
        {
            "memory_id": item["memory_id"],
            "record_type": item["record_type"],
            "role": item["role_hint"],
            "score": float(item["score"]),
            "reason": item["score_reason"],
            "source_ref": item["source_ref"],
        }
        for item in selected
    ]
    return {
        "retrieval_event_id": retrieval_event_id_for(proposal_id),
        "proposal_id": proposal_id,
        "campaign_id": campaign_id,
        "family": family,
        "lane": lane,
        "query_text": query_text,
        "query_tags": normalized_tags,
        "query_payload": query_payload,
        "items": items,
        "evidence": evidence,
        "created_at": utc_now_iso(),
    }


def _select_citations(*, family: str, preliminary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    source_kind_counts: dict[str, int] = {}
    source_refs: set[str] = set()

    def try_add(item: dict[str, Any]) -> bool:
        if source_kind_counts.get(str(item["source_kind"]), 0) >= 2:
            return False
        if str(item["source_ref"]) in source_refs:
            return False
        selected.append(item)
        source_kind_counts[str(item["source_kind"])] = source_kind_counts.get(str(item["source_kind"]), 0) + 1
        source_refs.add(str(item["source_ref"]))
        return True

    warnings = [item for item in preliminary if is_warning_record(item)]
    positives = [item for item in preliminary if is_positive_record(item)]
    if family == "combine":
        for item in positives:
            if len([entry for entry in selected if entry["role_hint"] == "combination_parent"]) >= 2:
                break
            if item["role_hint"] != "combination_parent":
                continue
            if selected and not all(are_mergeable_parent_records(item, other) for other in selected if other["role_hint"] == "combination_parent"):
                continue
            try_add(item)

    if warnings:
        try_add(warnings[0])
    if positives:
        try_add(positives[0])

    for item in preliminary:
        if len(selected) >= 4:
            break
        try_add(item)
    return selected[:4]


def _score_record(
    record: dict[str, Any],
    *,
    campaign_id: str,
    comparability_group: str,
    family: str,
    lane: str,
    tags: list[str],
    preferred_types: tuple[str, ...],
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if str(record.get("campaign_id") or "") == campaign_id:
        score += 8.0
        reasons.append("same campaign")
    elif str(record.get("comparability_group") or "") == comparability_group:
        score += 6.0
        reasons.append("same comparability group")
    overlap = len(set(tags) & set(record.get("tags") or []))
    if overlap:
        score += min(6.0, overlap * 2.0)
        reasons.append(f"{overlap} overlapping tags")
    if str(record.get("family") or "") == family:
        score += 2.0
        reasons.append("same family")
    if str(record.get("lane") or "") == lane:
        score += 1.0
        reasons.append("same lane")
    if str(record.get("record_type") or "") in preferred_types:
        score += 3.0
        reasons.append("preferred record type")
    outcome = str(record.get("outcome_label") or "")
    if outcome == "promoted" and family in {"exploit", "combine"}:
        score += 1.5
        reasons.append("positive outcome precedent")
    if outcome in {"failed", "discarded"} and family in {"novel", "exploit", "ablation"}:
        score += 1.5
        reasons.append("negative memory")
    recency_bonus = _recency_bonus(str(record.get("updated_at") or ""))
    if recency_bonus > 0:
        score += recency_bonus
        reasons.append("recent evidence")
    return score, reasons


def _recency_bonus(updated_at: str) -> float:
    if not updated_at:
        return 0.0
    candidate = updated_at[:-1] + "+00:00" if updated_at.endswith("Z") else updated_at
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return 0.0
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max((now - dt).total_seconds() / 86400.0, 0.0)
    return round(max(0.0, 1.0 - min(age_days / 365.0, 1.0)), 6)
