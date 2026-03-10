from __future__ import annotations

from typing import Any

from .idea_signatures import compute_idea_signature, scientific_mutation_paths


def normalize_proposal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    config_overrides = normalized.get("config_overrides", {})
    if not isinstance(config_overrides, dict):
        config_overrides = {}
    normalized["config_overrides"] = config_overrides
    normalized["parent_ids"] = [str(item) for item in list(normalized.get("parent_ids") or [])]
    normalized["tags"] = [str(item) for item in list(normalized.get("tags") or [])]
    normalized.setdefault("novelty_reason", None)
    normalized.setdefault("notes", None)
    normalized.setdefault("guardrails", {})
    normalized.setdefault("code_patch", None)
    normalized["source_experiments"] = [str(item) for item in list(normalized.get("source_experiments") or normalized.get("parent_ids", []))]
    normalized["mutation_paths"] = [str(item) for item in list(normalized.get("mutation_paths") or scientific_mutation_paths(config_overrides))]
    normalized["idea_signature"] = normalized.get("idea_signature") or compute_idea_signature(config_overrides)
    normalized["retrieval_event_id"] = normalized.get("retrieval_event_id")
    evidence_items = []
    for entry in list(normalized.get("evidence") or []):
        if not isinstance(entry, dict):
            continue
        evidence_items.append(
            {
                "memory_id": str(entry.get("memory_id") or ""),
                "record_type": str(entry.get("record_type") or ""),
                "role": str(entry.get("role") or "supporting_precedent"),
                "score": float(entry.get("score") or 0.0),
                "reason": str(entry.get("reason") or ""),
                "source_ref": str(entry.get("source_ref") or ""),
            }
        )
    normalized["evidence"] = evidence_items

    default_reason = "manual proposal"
    if str(normalized.get("generator") or "") == "scheduler":
        default_reason = "structured scheduler proposal"
    elif str(normalized.get("generator") or "") == "replay":
        default_reason = "replay proposal"
    generation_context = normalized.get("generation_context")
    if not isinstance(generation_context, dict):
        generation_context = {}
    normalized["generation_context"] = {
        "family_selector_reason": generation_context.get("family_selector_reason") or default_reason,
        "anchor_experiment_ids": list(generation_context.get("anchor_experiment_ids") or normalized.get("parent_ids", [])),
        "blocked_idea_signatures": list(generation_context.get("blocked_idea_signatures") or []),
        "retrieval_event_id": generation_context.get("retrieval_event_id", normalized.get("retrieval_event_id")),
        "selection_rank": generation_context.get("selection_rank"),
        "selection_score": generation_context.get("selection_score"),
    }
    return normalized
