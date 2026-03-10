from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..paths import LabPaths
from ..utils import read_json, utc_now_iso, write_json
from .profiles import DeviceProfile
from research.dense_gpt.search_space import estimate_peak_vram_gb

AUTOTUNE_VERSION = "1"
AUTOTUNE_VRAM_HEADROOM_GB = 2.0
SCOUT_COMPILE_OVERHEAD_THRESHOLD = 0.20
SCOUT_COMPILE_SPEEDUP_THRESHOLD = 0.05


@dataclass(frozen=True)
class RuntimeOverlayCandidate:
    device_batch_size: int
    eval_batch_size: int
    compile_enabled: bool

    def to_overlay(self) -> dict[str, Any]:
        return {
            "device_batch_size": int(self.device_batch_size),
            "eval_batch_size": int(self.eval_batch_size),
            "compile_enabled": bool(self.compile_enabled),
        }


@dataclass
class RuntimeAutotuneResult:
    campaign_id: str
    lane: str
    device_profile: str
    backend: str
    cache_key: str
    cache_path: Path
    autotune_version: str
    shape_family: str
    sequence_length: int
    runtime_defaults: dict[str, Any]
    from_cache: bool
    reason: str
    winner: dict[str, Any] | None
    candidates: list[dict[str, Any]]

    @property
    def runtime_overlay(self) -> dict[str, Any]:
        if not self.winner:
            return {}
        overlay = self.winner.get("runtime_overlay", {})
        return dict(overlay) if isinstance(overlay, dict) else {}

    @property
    def applied(self) -> bool:
        return bool(self.runtime_overlay)

    @property
    def runtime_effective(self) -> dict[str, Any]:
        effective = dict(self.runtime_defaults)
        effective.update(self.runtime_overlay)
        return effective

    def autotune_metadata(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "cache_key": self.cache_key,
            "cache_path": str(self.cache_path),
            "version": self.autotune_version,
            "from_cache": self.from_cache,
            "reason": self.reason,
            "shape_family": self.shape_family,
            "winner": self.winner,
            "runtime_defaults": self.runtime_defaults,
            "runtime_overlay": self.runtime_overlay,
        }

    def to_cache_payload(self) -> dict[str, Any]:
        return {
            "autotune_version": self.autotune_version,
            "created_at": utc_now_iso(),
            "campaign_id": self.campaign_id,
            "lane": self.lane,
            "device_profile": self.device_profile,
            "backend": self.backend,
            "cache_key": self.cache_key,
            "shape_family": self.shape_family,
            "sequence_length": self.sequence_length,
            "runtime_defaults": self.runtime_defaults,
            "reason": self.reason,
            "winner": self.winner,
            "candidates": self.candidates,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "lane": self.lane,
            "device_profile": self.device_profile,
            "backend": self.backend,
            "cache_key": self.cache_key,
            "cache_path": str(self.cache_path),
            "autotune_version": self.autotune_version,
            "shape_family": self.shape_family,
            "sequence_length": self.sequence_length,
            "from_cache": self.from_cache,
            "reason": self.reason,
            "runtime_defaults": self.runtime_defaults,
            "winner": self.winner,
            "candidates": self.candidates,
        }


def autotune_cache_dir(paths: LabPaths) -> Path:
    return paths.cache_root / "autotune"


def autotune_shape_family(resolved_config: dict[str, Any]) -> str:
    resolved = resolved_config["resolved"]
    model = resolved_config["model"]
    runtime = resolved_config.get("runtime", {})
    payload = {
        "depth": int(model["depth"]),
        "n_embd": int(resolved["n_embd"]),
        "n_head": int(resolved["n_head"]),
        "n_kv_head": int(resolved["n_kv_head"]),
        "head_dim": int(resolved["head_dim"]),
        "dtype": str(runtime.get("preferred_dtype", "bfloat16")),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def autotune_cache_key(
    *,
    device_profile: str,
    backend: str,
    campaign_id: str,
    lane: str,
    sequence_length: int,
    shape_family: str,
    autotune_version: str = AUTOTUNE_VERSION,
) -> str:
    payload = {
        "device_profile": device_profile,
        "backend": backend,
        "campaign_id": campaign_id,
        "lane": lane,
        "sequence_length": int(sequence_length),
        "shape_family": shape_family,
        "autotune_version": autotune_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest()


def autotune_cache_path(paths: LabPaths, cache_key: str) -> Path:
    return autotune_cache_dir(paths) / f"{cache_key}.json"


def default_runtime_probe_candidate_set(
    *,
    resolved_config: dict[str, Any],
    device_profile: DeviceProfile,
    backend: str,
) -> list[RuntimeOverlayCandidate]:
    runtime = resolved_config["runtime"]
    base_batch = max(1, int(runtime.get("device_batch_size", 1)))
    safe_ceiling = max(1, int(getattr(device_profile, "safe_device_batch_ceiling", base_batch) or base_batch))
    candidate_batches = {
        min(base_batch, safe_ceiling),
        min(max(1, int(math.ceil(base_batch * 1.25))), safe_ceiling),
        min(max(1, int(math.ceil(base_batch * 1.50))), safe_ceiling),
    }
    candidate_batches = {value for value in candidate_batches if value >= 1}
    if not candidate_batches:
        candidate_batches = {1}

    compile_choices = [False]
    if backend == "sdpa" and device_profile.supports_compile:
        base_compile = bool(runtime.get("compile_enabled", True))
        compile_choices = list(dict.fromkeys([base_compile, not base_compile]))

    candidates: list[RuntimeOverlayCandidate] = []
    for device_batch_size in sorted(candidate_batches):
        heuristic_eval = max(1, device_batch_size // 2)
        eval_batch_size = min(device_batch_size, heuristic_eval)
        if eval_batch_size < 1:
            eval_batch_size = 1
        for compile_enabled in compile_choices:
            candidates.append(
                RuntimeOverlayCandidate(
                    device_batch_size=device_batch_size,
                    eval_batch_size=eval_batch_size,
                    compile_enabled=bool(compile_enabled) and backend == "sdpa" and device_profile.supports_compile,
                )
            )
    return candidates


def load_runtime_autotune(
    paths: LabPaths,
    *,
    campaign: dict[str, Any],
    lane: str,
    device_profile: DeviceProfile,
    backend: str,
    resolved_config: dict[str, Any],
) -> RuntimeAutotuneResult | None:
    defaults = _runtime_defaults(resolved_config)
    shape_family = autotune_shape_family(resolved_config)
    cache_key = autotune_cache_key(
        device_profile=device_profile.profile_id,
        backend=backend,
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        sequence_length=int(resolved_config["resolved"]["sequence_length"]),
        shape_family=shape_family,
    )
    cache_path = autotune_cache_path(paths, cache_key)
    if not cache_path.exists():
        return None
    payload = read_json(cache_path)
    return RuntimeAutotuneResult(
        campaign_id=str(payload.get("campaign_id") or campaign["campaign_id"]),
        lane=str(payload.get("lane") or lane),
        device_profile=str(payload.get("device_profile") or device_profile.profile_id),
        backend=str(payload.get("backend") or backend),
        cache_key=str(payload.get("cache_key") or cache_key),
        cache_path=cache_path,
        autotune_version=str(payload.get("autotune_version") or AUTOTUNE_VERSION),
        shape_family=str(payload.get("shape_family") or shape_family),
        sequence_length=int(payload.get("sequence_length") or resolved_config["resolved"]["sequence_length"]),
        runtime_defaults=dict(payload.get("runtime_defaults") or defaults),
        from_cache=True,
        reason=str(payload.get("reason") or "cache hit"),
        winner=payload.get("winner") if isinstance(payload.get("winner"), dict) else None,
        candidates=list(payload.get("candidates") or []),
    )


def autotune_runtime(
    paths: LabPaths,
    *,
    campaign: dict[str, Any],
    lane: str,
    device_profile: DeviceProfile,
    backend: str,
    resolved_config: dict[str, Any],
    force: bool = False,
    probe_fn: Callable[[RuntimeOverlayCandidate], dict[str, Any]] | None = None,
) -> RuntimeAutotuneResult:
    cached = None if force else load_runtime_autotune(
        paths,
        campaign=campaign,
        lane=lane,
        device_profile=device_profile,
        backend=backend,
        resolved_config=resolved_config,
    )
    if cached is not None:
        return cached

    defaults = _runtime_defaults(resolved_config)
    shape_family = autotune_shape_family(resolved_config)
    cache_key = autotune_cache_key(
        device_profile=device_profile.profile_id,
        backend=backend,
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        sequence_length=int(resolved_config["resolved"]["sequence_length"]),
        shape_family=shape_family,
    )
    cache_path = autotune_cache_path(paths, cache_key)
    candidates = []
    for candidate in default_runtime_probe_candidate_set(
        resolved_config=resolved_config,
        device_profile=device_profile,
        backend=backend,
    ):
        probe = (probe_fn or (lambda item: probe_runtime_candidate(
            campaign=campaign,
            lane=lane,
            resolved_config=resolved_config,
            device_profile=device_profile,
            backend=backend,
            candidate=item,
        )))(candidate)
        probe.setdefault("runtime_overlay", candidate.to_overlay())
        candidates.append(probe)

    _apply_scout_compile_heuristic(candidates, lane=lane)
    eligible = [candidate for candidate in candidates if bool(candidate.get("eligible"))]
    winner = None
    reason = "no eligible candidate"
    if eligible:
        winner = max(
            eligible,
            key=lambda item: (
                float(item.get("tokens_per_second") or 0.0),
                float(item.get("vram_headroom_gb") or -1e9),
                1 if not bool(item.get("runtime_overlay", {}).get("compile_enabled")) else 0,
            ),
        )
        winner["selected"] = True
        reason = "probe selected"

    result = RuntimeAutotuneResult(
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        device_profile=device_profile.profile_id,
        backend=backend,
        cache_key=cache_key,
        cache_path=cache_path,
        autotune_version=AUTOTUNE_VERSION,
        shape_family=shape_family,
        sequence_length=int(resolved_config["resolved"]["sequence_length"]),
        runtime_defaults=defaults,
        from_cache=False,
        reason=reason,
        winner=winner,
        candidates=candidates,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(cache_path, result.to_cache_payload())
    return result


def resolve_runtime_autotune(
    paths: LabPaths,
    *,
    campaign: dict[str, Any],
    lane: str,
    device_profile: DeviceProfile,
    backend: str,
    resolved_config: dict[str, Any],
) -> RuntimeAutotuneResult:
    cached = load_runtime_autotune(
        paths,
        campaign=campaign,
        lane=lane,
        device_profile=device_profile,
        backend=backend,
        resolved_config=resolved_config,
    )
    if cached is not None:
        return cached
    shape_family = autotune_shape_family(resolved_config)
    cache_key = autotune_cache_key(
        device_profile=device_profile.profile_id,
        backend=backend,
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        sequence_length=int(resolved_config["resolved"]["sequence_length"]),
        shape_family=shape_family,
    )
    return RuntimeAutotuneResult(
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        device_profile=device_profile.profile_id,
        backend=backend,
        cache_key=cache_key,
        cache_path=autotune_cache_path(paths, cache_key),
        autotune_version=AUTOTUNE_VERSION,
        shape_family=shape_family,
        sequence_length=int(resolved_config["resolved"]["sequence_length"]),
        runtime_defaults=_runtime_defaults(resolved_config),
        from_cache=False,
        reason="cache miss",
        winner=None,
        candidates=[],
    )


def apply_runtime_autotune_metadata(
    resolved_config: dict[str, Any],
    autotune: RuntimeAutotuneResult,
) -> dict[str, Any]:
    config = copy.deepcopy(resolved_config)
    runtime = config.setdefault("runtime", {})
    runtime.update(autotune.runtime_overlay)
    runtime["autotune"] = autotune.autotune_metadata()
    return config


def probe_runtime_candidate(
    *,
    campaign: dict[str, Any],
    lane: str,
    resolved_config: dict[str, Any],
    device_profile: DeviceProfile,
    backend: str,
    candidate: RuntimeOverlayCandidate,
) -> dict[str, Any]:
    torch = _torch_module()
    if os.environ.get("LAB_AUTOTUNE_USE_CUDA_PROBE") == "1" and torch is not None and torch.cuda.is_available():
        return _probe_candidate_with_cuda(
            campaign=campaign,
            lane=lane,
            resolved_config=resolved_config,
            device_profile=device_profile,
            backend=backend,
            candidate=candidate,
        )
    return _probe_candidate_heuristic(
        campaign=campaign,
        lane=lane,
        resolved_config=resolved_config,
        device_profile=device_profile,
        backend=backend,
        candidate=candidate,
    )


def _probe_candidate_heuristic(
    *,
    campaign: dict[str, Any],
    lane: str,
    resolved_config: dict[str, Any],
    device_profile: DeviceProfile,
    backend: str,
    candidate: RuntimeOverlayCandidate,
) -> dict[str, Any]:
    config = copy.deepcopy(resolved_config)
    runtime = config.setdefault("runtime", {})
    runtime.update(candidate.to_overlay())
    peak_vram_gb = float(estimate_peak_vram_gb(config))
    budget = float(campaign["runtime"].get("max_peak_vram_gb", 0.0) or 0.0)
    headroom = None if budget <= 0 else round(budget - peak_vram_gb, 6)
    eligible = headroom is None or headroom >= AUTOTUNE_VRAM_HEADROOM_GB

    resolved = config["resolved"]
    width = max(1, int(resolved["n_embd"]))
    depth = max(1, int(config["model"]["depth"]))
    sequence_length = max(1, int(resolved["sequence_length"]))
    batch = candidate.device_batch_size
    profile_scale = 0.10 if device_profile.vendor == "cpu" else 1.0
    if device_profile.profile_id == "rtx_pro_6000_96gb":
        profile_scale = 2.40
    elif device_profile.profile_id == "generic_single_gpu_nvidia":
        profile_scale = 1.40
    backend_scale = {"kernels": 1.10, "sdpa": 1.00, "flex_attention": 0.95}.get(backend, 0.80)
    compile_speedup = 1.08 if candidate.compile_enabled and backend == "sdpa" and device_profile.supports_compile else 1.0
    complexity = max(1.0, float(depth * width * sequence_length) / 1_000_000.0)
    tokens_per_second = round(profile_scale * backend_scale * compile_speedup * float(batch * sequence_length) / complexity, 6)
    compile_seconds = round((0.35 if lane == "scout" else 0.18) * complexity, 6) if candidate.compile_enabled else 0.0
    total_seconds = round(max(0.05, (float(batch) / max(1.0, profile_scale * 64.0)) + compile_seconds), 6)

    payload = {
        "candidate_id": f"db{candidate.device_batch_size}_eb{candidate.eval_batch_size}_c{int(candidate.compile_enabled)}",
        "runtime_overlay": candidate.to_overlay(),
        "completed": True,
        "crash_class": None,
        "tokens_per_second": tokens_per_second,
        "peak_vram_gb": round(peak_vram_gb, 6),
        "vram_headroom_gb": headroom,
        "compile_seconds": compile_seconds,
        "total_seconds": total_seconds,
        "probe_mode": "heuristic",
        "eligible": bool(eligible),
        "disqualified_reason": None if eligible else "insufficient_vram_headroom",
    }
    return payload


def _probe_candidate_with_cuda(
    *,
    campaign: dict[str, Any],
    lane: str,
    resolved_config: dict[str, Any],
    device_profile: DeviceProfile,
    backend: str,
    candidate: RuntimeOverlayCandidate,
) -> dict[str, Any]:
    torch = _torch_module()
    if torch is None:
        return _probe_candidate_heuristic(
            campaign=campaign,
            lane=lane,
            resolved_config=resolved_config,
            device_profile=device_profile,
            backend=backend,
            candidate=candidate,
        )

    config = copy.deepcopy(resolved_config)
    config.setdefault("runtime", {}).update(candidate.to_overlay())
    budget = float(campaign["runtime"].get("max_peak_vram_gb", 0.0) or 0.0)
    runtime = config["runtime"]
    compile_enabled = bool(runtime.get("compile_enabled")) and backend == "sdpa" and device_profile.supports_compile and hasattr(torch, "compile")

    try:
        from research.dense_gpt.model import DenseGPT, DenseGPTConfig
        from research.dense_gpt.optim import build_optimizer
    except Exception:
        return _probe_candidate_heuristic(
            campaign=campaign,
            lane=lane,
            resolved_config=resolved_config,
            device_profile=device_profile,
            backend=backend,
            candidate=candidate,
        )

    model = None
    run_model = None
    optimizer = None
    try:
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        device = torch.device("cuda")
        model_config = DenseGPTConfig.from_resolved_config(config, backend=backend)
        model = DenseGPT(model_config).to(device)
        run_model = model
        compile_seconds = 0.0
        if compile_enabled:
            compile_started = time.perf_counter()
            run_model = torch.compile(model, dynamic=False)
            compile_seconds = time.perf_counter() - compile_started
        optimizer = build_optimizer(model, config)
        seq_len = int(config["resolved"]["sequence_length"])
        batch_size = int(runtime["device_batch_size"])
        vocab_size = int(config["resolved"]["vocab_size"])
        input_ids = torch.randint(0, vocab_size, (batch_size, seq_len), device=device, dtype=torch.long)
        targets = torch.roll(input_ids, shifts=-1, dims=1)
        autocast_dtype = _autocast_dtype(str(runtime.get("preferred_dtype", "bfloat16")), torch)
        steps = 2 if lane == "scout" else 3
        train_started = time.perf_counter()
        for _ in range(steps):
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=autocast_dtype, enabled=True):
                loss = run_model(input_ids, targets)
            loss.backward()
            optimizer.step()
        torch.cuda.synchronize()
        train_seconds = time.perf_counter() - train_started
        peak_vram_gb = round(torch.cuda.max_memory_allocated() / float(1024**3), 6)
        tokens_processed = int(input_ids.numel() * steps)
        total_seconds = round(train_seconds + compile_seconds, 6)
        headroom = None if budget <= 0 else round(budget - peak_vram_gb, 6)
        eligible = headroom is None or headroom >= AUTOTUNE_VRAM_HEADROOM_GB
        return {
            "candidate_id": f"db{candidate.device_batch_size}_eb{candidate.eval_batch_size}_c{int(candidate.compile_enabled)}",
            "runtime_overlay": candidate.to_overlay(),
            "completed": True,
            "crash_class": None,
            "tokens_per_second": round(0.0 if train_seconds <= 0 else tokens_processed / train_seconds, 6),
            "peak_vram_gb": peak_vram_gb,
            "vram_headroom_gb": headroom,
            "compile_seconds": round(compile_seconds, 6),
            "total_seconds": total_seconds,
            "probe_mode": "cuda_synthetic",
            "eligible": bool(eligible),
            "disqualified_reason": None if eligible else "insufficient_vram_headroom",
        }
    except RuntimeError as exc:
        crash_class = _classify_probe_runtime_error(str(exc), compile_enabled=compile_enabled)
        return {
            "candidate_id": f"db{candidate.device_batch_size}_eb{candidate.eval_batch_size}_c{int(candidate.compile_enabled)}",
            "runtime_overlay": candidate.to_overlay(),
            "completed": False,
            "crash_class": crash_class,
            "tokens_per_second": 0.0,
            "peak_vram_gb": None,
            "vram_headroom_gb": None,
            "compile_seconds": None,
            "total_seconds": None,
            "probe_mode": "cuda_synthetic",
            "eligible": False,
            "disqualified_reason": crash_class,
        }
    finally:
        del optimizer
        del run_model
        del model
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()


def _apply_scout_compile_heuristic(candidates: list[dict[str, Any]], *, lane: str) -> None:
    if lane != "scout":
        return
    non_compile_by_batch = {
        int(item.get("runtime_overlay", {}).get("device_batch_size") or 0): item
        for item in candidates
        if not bool(item.get("runtime_overlay", {}).get("compile_enabled"))
    }
    for candidate in candidates:
        runtime_overlay = candidate.get("runtime_overlay", {})
        if not bool(runtime_overlay.get("compile_enabled")):
            continue
        device_batch_size = int(runtime_overlay.get("device_batch_size") or 0)
        peer = non_compile_by_batch.get(device_batch_size)
        if peer is None or not bool(candidate.get("eligible")) or not bool(peer.get("completed")):
            continue
        total_seconds = float(candidate.get("total_seconds") or 0.0)
        compile_seconds = float(candidate.get("compile_seconds") or 0.0)
        if total_seconds <= 0:
            continue
        speedup = 0.0
        peer_tps = float(peer.get("tokens_per_second") or 0.0)
        if peer_tps > 0:
            speedup = (float(candidate.get("tokens_per_second") or 0.0) - peer_tps) / peer_tps
        if (compile_seconds / total_seconds) > SCOUT_COMPILE_OVERHEAD_THRESHOLD and speedup <= SCOUT_COMPILE_SPEEDUP_THRESHOLD:
            candidate["eligible"] = False
            candidate["disqualified_reason"] = "compile_overhead_dominates_scout"


def _runtime_defaults(resolved_config: dict[str, Any]) -> dict[str, Any]:
    runtime = resolved_config.get("runtime", {})
    return {
        "device_batch_size": int(runtime.get("device_batch_size", 1)),
        "eval_batch_size": int(runtime.get("eval_batch_size", max(1, int(runtime.get("device_batch_size", 1)) // 2))),
        "compile_enabled": bool(runtime.get("compile_enabled", True)),
    }


def _classify_probe_runtime_error(message: str, *, compile_enabled: bool) -> str:
    lowered = message.lower()
    if "out of memory" in lowered:
        return "oom_train"
    if compile_enabled and "compile" in lowered:
        return "compile_error"
    return "backend_unavailable"


def _autocast_dtype(preferred_dtype: str, torch_module) -> Any:
    if preferred_dtype == "float16":
        return torch_module.float16
    if preferred_dtype == "float32":
        return torch_module.float32
    return torch_module.bfloat16


def _torch_module():
    try:
        return importlib.import_module("torch")
    except Exception:
        return None


__all__ = [
    "AUTOTUNE_VERSION",
    "RuntimeAutotuneResult",
    "RuntimeOverlayCandidate",
    "apply_runtime_autotune_metadata",
    "autotune_cache_dir",
    "autotune_cache_key",
    "autotune_cache_path",
    "autotune_runtime",
    "autotune_shape_family",
    "default_runtime_probe_candidate_set",
    "load_runtime_autotune",
    "probe_runtime_candidate",
    "resolve_runtime_autotune",
]
