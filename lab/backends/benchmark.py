from __future__ import annotations

import importlib
import statistics
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ShapeFamily:
    family_id: str
    sequence_length: int
    batch_size: int
    head_count: int
    kv_head_count: int
    head_dim: int
    dtype: str
    causal: bool = True


@dataclass
class BenchmarkOutcome:
    candidate: "BackendCandidate"
    ok: bool
    median_ms: float | None
    reason: str


@dataclass(frozen=True)
class BackendCandidate:
    name: str
    version: str


def benchmark_backend(candidate: BackendCandidate, shape: ShapeFamily, *, repeats: int = 5) -> BenchmarkOutcome:
    torch = _torch_module()
    if torch is None or not torch.cuda.is_available():
        return BenchmarkOutcome(candidate, False, None, "CUDA unavailable")

    try:
        if candidate.name == "sdpa":
            median_ms = _benchmark_sdpa(torch, shape, repeats=repeats)
        elif candidate.name == "kernels":
            median_ms = _benchmark_kernels(torch, shape, repeats=repeats)
        elif candidate.name == "flex_attention":
            return BenchmarkOutcome(candidate, False, None, "flex attention benchmark harness not wired")
        else:
            return BenchmarkOutcome(candidate, False, None, "unsupported backend candidate")
    except Exception as exc:
        return BenchmarkOutcome(candidate, False, None, str(exc))
    return BenchmarkOutcome(candidate, True, median_ms, "benchmarked")


def benchmark_candidates(
    candidates: list[BackendCandidate],
    shape: ShapeFamily,
    *,
    benchmark_fn: Callable[[BackendCandidate, ShapeFamily], BenchmarkOutcome] | None = None,
) -> list[BenchmarkOutcome]:
    run = benchmark_fn or benchmark_backend
    return [run(candidate, shape) for candidate in candidates]


def _torch_module():
    try:
        return importlib.import_module("torch")
    except Exception:
        return None


def _dtype_from_name(torch, dtype_name: str):
    if dtype_name == "float16":
        return torch.float16
    if dtype_name == "float32":
        return torch.float32
    return torch.bfloat16


def _make_qkv(torch, shape: ShapeFamily):
    dtype = _dtype_from_name(torch, shape.dtype)
    q = torch.randn(shape.batch_size, shape.sequence_length, shape.head_count, shape.head_dim, device="cuda", dtype=dtype)
    k = torch.randn(shape.batch_size, shape.sequence_length, shape.kv_head_count, shape.head_dim, device="cuda", dtype=dtype)
    v = torch.randn(shape.batch_size, shape.sequence_length, shape.kv_head_count, shape.head_dim, device="cuda", dtype=dtype)
    return q, k, v


def _causal_mask(torch, sequence_length: int, window_size: int | None, *, device):
    positions = torch.arange(sequence_length, device=device)
    mask = positions[:, None] >= positions[None, :]
    if window_size is not None and window_size < sequence_length:
        mask = mask & (positions[:, None] - positions[None, :] < window_size)
    return mask


def _benchmark_sdpa(torch, shape: ShapeFamily, *, repeats: int) -> float:
    q, k, v = _make_qkv(torch, shape)
    q_sdpa = q.transpose(1, 2)
    k_sdpa = k.transpose(1, 2)
    v_sdpa = v.transpose(1, 2)
    if shape.head_count != shape.kv_head_count:
        factor = shape.head_count // shape.kv_head_count
        k_sdpa = k_sdpa.repeat_interleave(factor, dim=1)
        v_sdpa = v_sdpa.repeat_interleave(factor, dim=1)
    mask = _causal_mask(torch, shape.sequence_length, None, device=q.device)
    torch.cuda.synchronize()
    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        torch.nn.functional.scaled_dot_product_attention(q_sdpa, k_sdpa, v_sdpa, attn_mask=mask, is_causal=False)
        torch.cuda.synchronize()
        timings.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(timings))


def _benchmark_kernels(torch, shape: ShapeFamily, *, repeats: int) -> float:
    kernels = importlib.import_module("kernels")
    capability = torch.cuda.get_device_capability()
    repo = "varunneal/flash-attention-3" if capability == (9, 0) else "kernels-community/flash-attn3"
    flash_attn = kernels.get_kernel(repo).flash_attn_interface.flash_attn_func
    q, k, v = _make_qkv(torch, shape)
    torch.cuda.synchronize()
    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        flash_attn(q, k, v, causal=shape.causal, window_size=(-1, -1))
        torch.cuda.synchronize()
        timings.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(timings))


__all__ = ["BackendCandidate", "BenchmarkOutcome", "ShapeFamily", "benchmark_backend", "benchmark_candidates"]
