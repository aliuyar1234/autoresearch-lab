from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any


def _normalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _normalize(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _normalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, set):
        return [_normalize(v) for v in sorted(value, key=repr)]
    if isinstance(value, Path):
        return str(value.as_posix())
    if isinstance(value, float):
        # Rely on JSON encoder for stable finite float rendering after normalization.
        return value
    return value


def canonical_json_bytes(value: Any) -> bytes:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def short_fingerprint(value: Any, length: int = 12) -> str:
    return stable_fingerprint(value)[:length]
