from __future__ import annotations

from copy import deepcopy
from typing import Any

__all__ = [
    "disjoint_mergeable",
    "flatten_override_paths",
    "make_ablation_override",
    "make_combine_override",
    "merge_nested_dicts",
    "unflatten_override_paths",
]


def merge_nested_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(left)
    for key, value in right.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge_nested_dicts(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in sorted(payload.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(flatten_override_paths(value, path))
        else:
            items.append((path, value))
    return items


def unflatten_override_paths(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in items:
        cursor = out
        parts = path.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return out


def make_ablation_override(parent_overrides: dict[str, Any], remove_path: str) -> dict[str, Any]:
    items = [(path, value) for path, value in flatten_override_paths(parent_overrides) if path != remove_path]
    return unflatten_override_paths(items)


def disjoint_mergeable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_paths = {path for path, _ in flatten_override_paths(left)}
    right_paths = {path for path, _ in flatten_override_paths(right)}
    return left_paths.isdisjoint(right_paths)


def make_combine_override(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if not disjoint_mergeable(left, right):
        raise ValueError("combine only supports disjoint override paths")
    return merge_nested_dicts(left, right)
