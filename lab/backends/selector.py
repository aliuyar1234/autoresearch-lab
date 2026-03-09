from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .benchmark import BackendCandidate, BenchmarkOutcome, ShapeFamily, benchmark_candidates
from .cache import append_blacklist_entry, is_blacklisted, load_backend_blacklist, load_backend_cache, save_backend_cache
from .profiles import DeviceProfile


@dataclass
class BackendSelection:
    backend: str
    version: str
    device_profile: DeviceProfile
    shape: ShapeFamily
    reason: str
    from_cache: bool
    benchmark_results: list[BenchmarkOutcome]
    cache_path: Path
    blacklist_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "version": self.version,
            "device_profile": self.device_profile.to_dict(),
            "shape": asdict(self.shape),
            "reason": self.reason,
            "from_cache": self.from_cache,
            "benchmark_results": [
                {
                    "candidate": outcome.candidate.name,
                    "version": outcome.candidate.version,
                    "ok": outcome.ok,
                    "median_ms": outcome.median_ms,
                    "reason": outcome.reason,
                }
                for outcome in self.benchmark_results
            ],
            "cache_path": str(self.cache_path),
            "blacklist_path": str(self.blacklist_path),
        }


def backend_cache_path(paths) -> Path:
    return paths.cache_root / "backend_selector_cache.json"


def backend_blacklist_path(paths) -> Path:
    return paths.cache_root / "backend_selector_blacklist.json"


def cache_key(
    *,
    device_profile: str,
    cuda_version: str | None,
    torch_version: str,
    shape: ShapeFamily,
    compile_enabled: bool,
) -> str:
    payload = {
        "device_profile": device_profile,
        "cuda_version": cuda_version or "unknown",
        "torch_version": torch_version,
        "shape": asdict(shape),
        "compile_enabled": bool(compile_enabled),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def available_backend_candidates(device_profile: DeviceProfile) -> list[BackendCandidate]:
    candidates: list[BackendCandidate] = []
    torch = _torch_module()
    if torch is not None and torch.cuda.is_available():
        candidates.append(BackendCandidate("sdpa", getattr(torch, "__version__", "unknown")))
    if device_profile.supports_flash_attention:
        try:
            kernels = importlib.import_module("kernels")
            candidates.append(BackendCandidate("kernels", getattr(kernels, "__version__", "unknown")))
        except Exception:
            pass
    if device_profile.supports_flex_attention:
        candidates.append(BackendCandidate("flex_attention", getattr(torch, "__version__", "unknown") if torch is not None else "unknown"))
    return candidates


def shape_family_for_run(
    campaign: dict[str, Any],
    config: dict[str, Any],
    device_profile: DeviceProfile,
    *,
    purpose: str = "train",
) -> ShapeFamily:
    resolved = config["resolved"]
    runtime = config["runtime"]
    device_batch = int(runtime["device_batch_size"])
    eval_batch = int(runtime.get("eval_batch_size", max(1, device_batch // 2)))
    batch_size = eval_batch if purpose == "eval" else device_batch
    batch_size = max(1, min(batch_size, int(device_profile.safe_device_batch_ceiling)))
    return ShapeFamily(
        family_id=f"{campaign['campaign_id']}_{purpose}",
        sequence_length=int(resolved["sequence_length"]),
        batch_size=batch_size,
        head_count=int(resolved["n_head"]),
        kv_head_count=int(resolved["n_kv_head"]),
        head_dim=int(resolved["head_dim"]),
        dtype=str(runtime.get("preferred_dtype", device_profile.preferred_dtype)),
        causal=True,
    )


def select_backend(
    *,
    cache_path: Path,
    blacklist_path: Path,
    candidates: list[BackendCandidate],
    shape: ShapeFamily,
    device_profile: DeviceProfile,
    cuda_version: str | None,
    torch_version: str,
    compile_enabled: bool,
    force_rebenchmark: bool = False,
    benchmark_fn: Callable[[BackendCandidate, ShapeFamily], BenchmarkOutcome] | None = None,
) -> BackendSelection:
    cache = load_backend_cache(cache_path)
    blacklist = load_backend_blacklist(blacklist_path)
    key = cache_key(
        device_profile=device_profile.profile_id,
        cuda_version=cuda_version,
        torch_version=torch_version,
        shape=shape,
        compile_enabled=compile_enabled,
    )

    cached = cache.get(key)
    if cached and not force_rebenchmark and not is_blacklisted(blacklist, backend=str(cached["backend"]), shape_family=shape.family_id):
        return BackendSelection(
            backend=str(cached["backend"]),
            version=str(cached.get("version", "unknown")),
            device_profile=device_profile,
            shape=shape,
            reason="cache hit",
            from_cache=True,
            benchmark_results=[],
            cache_path=cache_path,
            blacklist_path=blacklist_path,
        )

    outcomes = benchmark_candidates(candidates, shape, benchmark_fn=benchmark_fn)
    valid = [outcome for outcome in outcomes if outcome.ok and outcome.median_ms is not None]
    valid = [outcome for outcome in valid if not is_blacklisted(blacklist, backend=outcome.candidate.name, shape_family=shape.family_id)]
    if not valid:
        fallback = _fallback_candidate(candidates)
        reason = "no valid backend"
        if fallback is not None:
            return BackendSelection(
                backend=fallback.name,
                version=fallback.version,
                device_profile=device_profile,
                shape=shape,
                reason=reason,
                from_cache=False,
                benchmark_results=outcomes,
                cache_path=cache_path,
                blacklist_path=blacklist_path,
            )
        return BackendSelection(
            backend="unknown_backend",
            version="unknown",
            device_profile=device_profile,
            shape=shape,
            reason=reason,
            from_cache=False,
            benchmark_results=outcomes,
            cache_path=cache_path,
            blacklist_path=blacklist_path,
        )

    best = min(valid, key=lambda item: float(item.median_ms))
    cache[key] = {
        "backend": best.candidate.name,
        "version": best.candidate.version,
        "median_ms": best.median_ms,
        "shape_family": shape.family_id,
    }
    save_backend_cache(cache_path, cache)
    return BackendSelection(
        backend=best.candidate.name,
        version=best.candidate.version,
        device_profile=device_profile,
        shape=shape,
        reason="bench selected",
        from_cache=False,
        benchmark_results=outcomes,
        cache_path=cache_path,
        blacklist_path=blacklist_path,
    )


def record_backend_failure(paths, *, backend: str, shape_family: str, reason: str) -> None:
    append_blacklist_entry(backend_blacklist_path(paths), backend=backend, shape_family=shape_family, reason=reason)


def _torch_module():
    try:
        return importlib.import_module("torch")
    except Exception:
        return None


def _fallback_candidate(candidates: list[BackendCandidate]) -> BackendCandidate | None:
    for name in ("sdpa", "kernels", "flex_attention"):
        for candidate in candidates:
            if candidate.name == name:
                return candidate
    return candidates[0] if candidates else None


__all__ = [
    "BackendSelection",
    "available_backend_candidates",
    "backend_blacklist_path",
    "backend_cache_path",
    "cache_key",
    "record_backend_failure",
    "select_backend",
    "shape_family_for_run",
]
