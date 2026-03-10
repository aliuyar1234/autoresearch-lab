from __future__ import annotations

import json
from hashlib import sha1
from typing import Any

RUNTIME_ONLY_PREFIXES = (
    "runtime.device_batch_size",
    "runtime.eval_batch_size",
    "runtime.compile_enabled",
    "runtime.autotune_",
    "runtime.autotune",
    "runtime.backend_cache",
)


def scientific_mutation_items(config_overrides: dict[str, Any]) -> list[tuple[str, Any]]:
    items = _flatten_override_paths(config_overrides)
    return [(path, value) for path, value in items if not _is_runtime_only_path(path)]


def scientific_mutation_paths(config_overrides: dict[str, Any]) -> list[str]:
    return [path for path, _ in scientific_mutation_items(config_overrides)]


def compute_idea_signature(config_overrides: dict[str, Any]) -> str:
    normalized = [[path, _normalize_value(value)] for path, value in scientific_mutation_items(config_overrides)]
    digest = sha1(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"sig_{digest[:16]}"


def _is_runtime_only_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in RUNTIME_ONLY_PREFIXES)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return format(value, ".4g")
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in sorted(value.items())}
    return value


def _flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in sorted(payload.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(_flatten_override_paths(value, path))
        else:
            items.append((path, value))
    return items
