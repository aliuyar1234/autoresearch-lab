from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


def novelty_counter(overrides_payloads: Iterable[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for overrides in overrides_payloads:
        counts.update(novelty_tags(overrides))
    return counts


def novelty_tags(config_overrides: dict[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []
    flat = _flatten_override_paths(config_overrides)
    for path, value in flat:
        tags.append(path)
        if isinstance(value, (int, float)):
            magnitude = "small" if abs(float(value)) < 2 else "large"
            tags.append(f"{path}:{magnitude}")
        else:
            tags.append(f"{path}:{value}")
    return tuple(sorted(set(tags)))


def _flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in sorted(payload.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(_flatten_override_paths(value, path))
        else:
            items.append((path, value))
    return items


__all__ = ["novelty_counter", "novelty_tags"]
