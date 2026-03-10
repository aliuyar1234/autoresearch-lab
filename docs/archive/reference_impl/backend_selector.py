from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Callable, Iterable, Any


@dataclasses.dataclass(frozen=True)
class BackendCandidate:
    name: str
    version: str


@dataclasses.dataclass(frozen=True)
class ShapeFamily:
    family_id: str
    sequence_length: int
    batch_size: int
    head_dim: int
    dtype: str


@dataclasses.dataclass
class BenchmarkOutcome:
    candidate: BackendCandidate
    ok: bool
    median_ms: float | None
    reason: str


def cache_key(
    *,
    device_profile: str,
    cuda_version: str,
    torch_version: str,
    shape: ShapeFamily,
    compile_enabled: bool,
) -> str:
    payload = {
        "device_profile": device_profile,
        "cuda_version": cuda_version,
        "torch_version": torch_version,
        "shape": dataclasses.asdict(shape),
        "compile_enabled": compile_enabled,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def select_backend(
    *,
    candidates: Iterable[BackendCandidate],
    shape: ShapeFamily,
    device_profile: str,
    cuda_version: str,
    torch_version: str,
    compile_enabled: bool,
    benchmark_fn: Callable[[BackendCandidate, ShapeFamily], tuple[bool, float | None, str]],
    cache_path: Path,
    blacklist: set[tuple[str, str]] | None = None,
) -> BenchmarkOutcome:
    blacklist = blacklist or set()
    key = cache_key(
        device_profile=device_profile,
        cuda_version=cuda_version,
        torch_version=torch_version,
        shape=shape,
        compile_enabled=compile_enabled,
    )

    cache = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    cached = cache.get(key)
    if cached and (cached["candidate"], shape.family_id) not in blacklist:
        return BenchmarkOutcome(
            candidate=BackendCandidate(cached["candidate"], cached.get("version", "unknown")),
            ok=True,
            median_ms=float(cached["median_ms"]),
            reason="cache hit",
        )

    outcomes: list[BenchmarkOutcome] = []
    for candidate in candidates:
        if (candidate.name, shape.family_id) in blacklist:
            outcomes.append(BenchmarkOutcome(candidate, False, None, "blacklisted"))
            continue
        ok, median_ms, reason = benchmark_fn(candidate, shape)
        outcomes.append(BenchmarkOutcome(candidate, ok, median_ms, reason))

    valid = [o for o in outcomes if o.ok and o.median_ms is not None]
    if not valid:
        return BenchmarkOutcome(BackendCandidate("none", "none"), False, None, "no valid backend")

    best = min(valid, key=lambda o: o.median_ms)
    cache[key] = {
        "candidate": best.candidate.name,
        "version": best.candidate.version,
        "median_ms": best.median_ms,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    best.reason = "bench selected"
    return best
