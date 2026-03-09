from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..utils import utc_now_iso, write_json


def load_json_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_backend_cache(path: Path) -> dict[str, Any]:
    return load_json_map(path)


def save_backend_cache(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def load_backend_blacklist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def save_backend_blacklist(path: Path, entries: list[dict[str, Any]]) -> None:
    write_json(path, entries)


def is_blacklisted(entries: list[dict[str, Any]], *, backend: str, shape_family: str) -> bool:
    return any(
        str(entry.get("backend")) == backend and str(entry.get("shape_family")) == shape_family
        for entry in entries
    )


def append_blacklist_entry(path: Path, *, backend: str, shape_family: str, reason: str) -> None:
    entries = load_backend_blacklist(path)
    if is_blacklisted(entries, backend=backend, shape_family=shape_family):
        return
    entries.append(
        {
            "backend": backend,
            "shape_family": shape_family,
            "reason": reason,
            "created_at": utc_now_iso(),
        }
    )
    save_backend_blacklist(path, entries)


__all__ = [
    "append_blacklist_entry",
    "is_blacklisted",
    "load_backend_blacklist",
    "load_backend_cache",
    "load_json_map",
    "save_backend_blacklist",
    "save_backend_cache",
]
