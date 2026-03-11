from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import load_schema, read_json, utc_now_iso, validate_payload, write_json

POLICY_FAMILIES = ("baseline", "exploit", "ablation", "combine", "novel")


def scheduler_policy_root(paths, campaign_id: str) -> Path:
    return paths.artifacts_root / "policies" / campaign_id


def reviewed_scheduler_policy_path(paths, campaign_id: str) -> Path:
    return scheduler_policy_root(paths, campaign_id) / "active_reviewed_policy.json"


def load_reviewed_scheduler_policy(paths, campaign_id: str) -> dict[str, Any] | None:
    path = reviewed_scheduler_policy_path(paths, campaign_id)
    if not path.exists():
        return None
    payload = read_json(path)
    if not isinstance(payload, dict):
        return None
    schema = load_schema(paths.schemas_root / "agent_scheduler_policy.schema.json")
    validate_payload(payload, schema)
    if str(payload.get("campaign_id") or "") != str(campaign_id):
        return None
    if str(payload.get("review_state") or "") != "reviewed":
        return None
    return payload


def write_scheduler_policy_suggestion(
    *,
    paths,
    campaign_id: str,
    family_weights: dict[str, float],
    preferred_families: list[str],
    blocked_families: list[str],
    rationale: str,
    notes: list[str] | None = None,
    review_state: str = "draft",
) -> Path:
    timestamp = utc_now_iso()
    policy = {
        "policy_id": f"policy_{campaign_id}_{_safe_stamp(timestamp)}",
        "campaign_id": campaign_id,
        "review_state": review_state,
        "family_weights": {
            family: float(family_weights.get(family, 1.0))
            for family in POLICY_FAMILIES
        },
        "preferred_families": [family for family in preferred_families if family in POLICY_FAMILIES],
        "blocked_families": [family for family in blocked_families if family in POLICY_FAMILIES],
        "max_complexity_cost": None,
        "rationale": rationale,
        "notes": list(notes or []),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    validate_payload(policy, load_schema(paths.schemas_root / "agent_scheduler_policy.schema.json"))
    root = scheduler_policy_root(paths, campaign_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "suggestions" / f"{policy['policy_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, policy)
    return path


def policy_summary(policy: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(policy, dict):
        return None
    family_weights = {
        family: float(policy.get("family_weights", {}).get(family, 1.0))
        for family in POLICY_FAMILIES
    }
    return {
        "policy_id": policy.get("policy_id"),
        "review_state": policy.get("review_state"),
        "preferred_families": [family for family in policy.get("preferred_families", []) if family in POLICY_FAMILIES],
        "blocked_families": [family for family in policy.get("blocked_families", []) if family in POLICY_FAMILIES],
        "family_weights": family_weights,
        "rationale": policy.get("rationale"),
        "notes": list(policy.get("notes") or []),
        "updated_at": policy.get("updated_at"),
    }


def _safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z").replace("T", "_")


__all__ = [
    "POLICY_FAMILIES",
    "load_reviewed_scheduler_policy",
    "policy_summary",
    "reviewed_scheduler_policy_path",
    "scheduler_policy_root",
    "write_scheduler_policy_suggestion",
]
