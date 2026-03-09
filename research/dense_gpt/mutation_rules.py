from __future__ import annotations

from typing import Any


def merge_nested_dicts(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_nested_dicts(dict(merged[key]), value)
        elif isinstance(value, dict):
            merged[key] = merge_nested_dicts({}, value)
        else:
            merged[key] = value
    return merged


def apply_path_override(base_overrides: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    cursor: dict[str, Any] = {}
    root = cursor
    parts = path.split(".")
    for part in parts[:-1]:
        child: dict[str, Any] = {}
        cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value
    return merge_nested_dicts(dict(base_overrides), root)


def mutation_respects_campaign_constraints(
    campaign: dict[str, Any],
    overrides: dict[str, Any],
    *,
    device_profile: Any | None = None,
) -> tuple[bool, list[str]]:
    from .search_space import validate_dense_config, resolve_dense_config

    resolved = resolve_dense_config(campaign, overrides, device_profile=device_profile)
    issues = validate_dense_config(campaign, resolved, device_profile=device_profile)
    return not issues, issues


__all__ = ["apply_path_override", "merge_nested_dicts", "mutation_respects_campaign_constraints"]
