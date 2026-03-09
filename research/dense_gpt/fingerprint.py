from __future__ import annotations

from typing import Any

from reference_impl.config_fingerprint import canonical_json_bytes, short_fingerprint, stable_fingerprint

__all__ = ["canonical_json_bytes", "short_fingerprint", "stable_fingerprint", "fingerprint_config"]


def fingerprint_config(config: Any, *, short: bool = False, length: int = 12) -> str:
    if short:
        return short_fingerprint(config, length=length)
    return stable_fingerprint(config)
