from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from .defaults import base_config_for_campaign
from .mutation_rules import apply_path_override, merge_nested_dicts


@dataclass(frozen=True)
class SearchKnob:
    path: str
    values: tuple[Any, ...]
    tag: str
    hypothesis: str
    rationale: str
    lanes: tuple[str, ...] = ("scout", "main", "confirm")


def _rounded_width(depth: int, aspect_ratio: int, head_dim: int) -> int:
    width = depth * aspect_ratio
    return max(head_dim, int(math.ceil(width / head_dim) * head_dim))


def _kv_heads_for_ratio(n_head: int, ratio: str) -> int:
    if ratio == "full":
        return n_head
    if ratio == "half":
        return max(1, n_head // 2)
    if ratio == "quarter":
        return max(1, n_head // 4)
    raise ValueError(f"unsupported kv ratio: {ratio}")


def _normalize_bool_leafs(config: dict[str, Any]) -> dict[str, Any]:
    normalized = merge_nested_dicts({}, config)
    curriculum = normalized.setdefault("curriculum", {})
    seq = curriculum.get("sequence_curriculum")
    if isinstance(seq, bool):
        curriculum["sequence_curriculum"] = {"enabled": seq, "start_fraction": 0.5}
    prog = curriculum.get("progressive_depth")
    if isinstance(prog, bool):
        curriculum["progressive_depth"] = {"enabled": prog, "warmup_fraction": 0.45, "min_depth": 4}
    return normalized


def resolve_dense_config(
    campaign: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    *,
    device_profile: Any | None = None,
) -> dict[str, Any]:
    merged = base_config_for_campaign(campaign, device_profile=device_profile)
    if overrides:
        merged = merge_nested_dicts(merged, overrides)
    merged = _normalize_bool_leafs(merged)

    model = merged.setdefault("model", {})
    depth = int(model["depth"])
    aspect_ratio = int(model["aspect_ratio"])
    head_dim = int(model["head_dim"])
    model["n_embd"] = _rounded_width(depth, aspect_ratio, head_dim)
    model["n_head"] = int(model["n_embd"] // head_dim)
    if "n_kv_head" in model:
        model["n_kv_head"] = int(model["n_kv_head"])
    else:
        model["n_kv_head"] = _kv_heads_for_ratio(int(model["n_head"]), str(model.get("kv_head_ratio", "full")))
    model.setdefault("kv_head_ratio", "custom" if "n_kv_head" in (overrides or {}).get("model", {}) else "full")

    runtime = merged.setdefault("runtime", {})
    runtime.setdefault("compile_enabled", True)
    runtime.setdefault("device_batch_size", 128)
    runtime.setdefault("eval_batch_size", max(1, int(runtime["device_batch_size"]) // 2))
    runtime.setdefault("preferred_dtype", "bfloat16")
    if device_profile is not None:
        runtime["detected_device_profile"] = getattr(device_profile, "profile_id", None)

    merged["resolved"] = {
        "sequence_length": int(campaign["sequence_length"]),
        "vocab_size": int(campaign["vocab_size"]),
        "n_embd": model["n_embd"],
        "n_head": model["n_head"],
        "n_kv_head": model["n_kv_head"],
        "head_dim": head_dim,
    }
    return merged


def estimate_peak_vram_gb(config: dict[str, Any]) -> float:
    resolved = config["resolved"]
    runtime = config["runtime"]
    depth = int(config["model"]["depth"])
    seq_len = int(resolved["sequence_length"])
    width = int(resolved["n_embd"])
    batch = int(runtime["device_batch_size"])
    params = depth * width * width * 12
    activations = depth * seq_len * width * batch * 4
    bytes_total = (params * 2.0) + (activations * 2.0)
    return round(bytes_total / float(1024**3), 3)


def validate_dense_config(
    campaign: dict[str, Any],
    config: dict[str, Any],
    *,
    device_profile: Any | None = None,
) -> list[str]:
    issues: list[str] = []
    model = config["model"]
    runtime = config["runtime"]
    curriculum = config["curriculum"]
    resolved = config["resolved"]

    depth = int(model["depth"])
    aspect_ratio = int(model["aspect_ratio"])
    head_dim = int(model["head_dim"])
    n_head = int(model["n_head"])
    n_kv_head = int(model["n_kv_head"])
    window_pattern = str(model["window_pattern"]).upper()
    rope_base = int(model["rope_base"])

    if depth < 4 or depth > 24:
        issues.append("model.depth must stay between 4 and 24")
    if aspect_ratio < 32 or aspect_ratio > 160 or aspect_ratio % 8 != 0:
        issues.append("model.aspect_ratio must stay in [32, 160] and be divisible by 8")
    if head_dim < 32 or head_dim > 192 or head_dim % 32 != 0:
        issues.append("model.head_dim must stay in [32, 192] and be divisible by 32")
    if n_head < 2 or n_head > 32:
        issues.append("resolved n_head must stay between 2 and 32")
    if n_kv_head < 1 or n_kv_head > n_head or n_head % n_kv_head != 0:
        issues.append("model.n_kv_head must divide model.n_head and stay within range")
    if len(window_pattern) < 4 or len(window_pattern) > 8 or any(char not in {"S", "L"} for char in window_pattern):
        issues.append("model.window_pattern must be 4-8 characters using only S and L")
    if window_pattern and window_pattern[-1] != "L":
        issues.append("model.window_pattern must end with L so the last block sees full context")
    if rope_base < 1_000:
        issues.append("model.rope_base must be >= 1000")
    if int(config["campaign"]["sequence_length"]) != int(campaign["sequence_length"]):
        issues.append("campaign sequence length drifted during config resolution")
    if int(config["campaign"]["vocab_size"]) != int(campaign["vocab_size"]):
        issues.append("campaign vocab size drifted during config resolution")
    if int(runtime["device_batch_size"]) < 1:
        issues.append("runtime.device_batch_size must be >= 1")
    if int(runtime["eval_batch_size"]) < 1:
        issues.append("runtime.eval_batch_size must be >= 1")

    seq_curriculum = curriculum["sequence_curriculum"]
    prog_depth = curriculum["progressive_depth"]
    if not 0.0 <= float(seq_curriculum["start_fraction"]) <= 1.0:
        issues.append("curriculum.sequence_curriculum.start_fraction must be between 0 and 1")
    if not 0.0 <= float(prog_depth["warmup_fraction"]) <= 1.0:
        issues.append("curriculum.progressive_depth.warmup_fraction must be between 0 and 1")
    if int(prog_depth["min_depth"]) < 1 or int(prog_depth["min_depth"]) > depth:
        issues.append("curriculum.progressive_depth.min_depth must stay between 1 and model.depth")
    if float(config["schedule"]["warmdown_ratio"]) < 0.0 or float(config["schedule"]["warmdown_ratio"]) > 1.0:
        issues.append("schedule.warmdown_ratio must stay between 0 and 1")

    if device_profile is not None:
        ceiling = getattr(device_profile, "safe_device_batch_ceiling", None)
        if ceiling is not None and int(runtime["device_batch_size"]) > int(ceiling):
            issues.append("runtime.device_batch_size exceeds device profile safe ceiling")

    peak_vram = estimate_peak_vram_gb(config)
    max_peak_vram = float(campaign["runtime"].get("max_peak_vram_gb", 0.0) or 0.0)
    if max_peak_vram and peak_vram > max_peak_vram:
        issues.append("estimated peak VRAM exceeds campaign runtime guardrail")

    if resolved["n_embd"] % head_dim != 0:
        issues.append("resolved n_embd must remain divisible by model.head_dim")

    return issues


def estimate_complexity_cost(
    campaign: dict[str, Any],
    overrides: dict[str, Any],
    *,
    device_profile: Any | None = None,
) -> int:
    resolved = resolve_dense_config(campaign, overrides, device_profile=device_profile)
    issues = validate_dense_config(campaign, resolved, device_profile=device_profile)
    if issues:
        return 9
    weights = {
        "model.depth": 2,
        "model.aspect_ratio": 2,
        "model.head_dim": 2,
        "model.n_kv_head": 2,
        "model.window_pattern": 2,
        "model.rope_base": 1,
        "model.ema_at_eval": 1,
        "optimizer_groups.embed_lr_scale": 1,
        "optimizer_groups.unembed_lr_scale": 1,
        "optimizer_groups.matrix_lr_scale": 1,
        "optimizer_groups.scalar_lr_scale": 1,
        "optimizer_groups.weight_decay": 1,
        "schedule.warmdown_ratio": 1,
        "curriculum.sequence_curriculum.enabled": 1,
        "curriculum.progressive_depth.enabled": 1,
    }
    cost = 0
    for path in flatten_override_paths(overrides):
        cost += weights.get(path, 1)
    return max(0, min(9, cost))


def flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths.extend(flatten_override_paths(value, path))
        else:
            paths.append(path)
    return paths


def search_knobs_for_campaign(
    campaign: dict[str, Any],
    lane: str,
    *,
    device_profile: Any | None = None,
) -> tuple[SearchKnob, ...]:
    defaults = resolve_dense_config(campaign, {}, device_profile=device_profile)
    n_head = int(defaults["model"]["n_head"])
    kv_values = tuple(
        value
        for value in (
            n_head,
            max(1, n_head // 2),
            max(1, n_head // 4),
        )
        if n_head % value == 0
    )

    knob_pool = (
        SearchKnob(
            path="model.depth",
            values=tuple(value for value in (defaults["model"]["depth"] - 2, defaults["model"]["depth"] + 2) if 4 <= value <= 24),
            tag="depth",
            hypothesis="Small depth shifts may use the same wall-clock budget more effectively.",
            rationale="Depth is a first-class dense-model knob and should be searchable without code edits.",
        ),
        SearchKnob(
            path="model.aspect_ratio",
            values=tuple(
                value
                for value in (
                    defaults["model"]["aspect_ratio"] - 8,
                    defaults["model"]["aspect_ratio"] + 8,
                    defaults["model"]["aspect_ratio"] + 16,
                )
                if 32 <= value <= 160 and value % 8 == 0
            ),
            tag="aspect_ratio",
            hypothesis="Width scaling may shift the best compute allocation for this campaign.",
            rationale="Aspect ratio changes model width while staying in the dense single-GPU regime.",
        ),
        SearchKnob(
            path="model.head_dim",
            values=tuple(value for value in (64, 96, 128, 160) if value != defaults["model"]["head_dim"]),
            tag="head_dim",
            hypothesis="Attention head geometry may be under-tuned for the current sequence length.",
            rationale="Head dimension changes both head count and runtime shape family.",
        ),
        SearchKnob(
            path="model.n_kv_head",
            values=kv_values,
            tag="n_kv_head",
            hypothesis="KV sharing could trade a little flexibility for much better runtime efficiency.",
            rationale="KV head count is a required dense-model search knob for this lab.",
        ),
        SearchKnob(
            path="model.window_pattern",
            values=("SLSL", "SSLL", "LLSL", "LLLL"),
            tag="window_pattern",
            hypothesis="Window pattern may be limiting useful context integration.",
            rationale="Window pattern is an architecture knob that remains compile-friendly.",
        ),
        SearchKnob(
            path="optimizer_groups.embed_lr_scale",
            values=(0.90, 1.10, 1.25),
            tag="embed_lr",
            hypothesis="Embedding updates may be under- or over-tuned relative to the rest of the model.",
            rationale="Embedding LR scale is cheap, comparable, and often interacts strongly with the fixed budget.",
        ),
        SearchKnob(
            path="optimizer_groups.unembed_lr_scale",
            values=(0.85, 1.10),
            tag="unembed_lr",
            hypothesis="Unembedding updates may need a different pace than the embedding table.",
            rationale="Unembedding LR is a separate dense-model knob in the lab search surface.",
        ),
        SearchKnob(
            path="optimizer_groups.matrix_lr_scale",
            values=(0.90, 1.10),
            tag="matrix_lr",
            hypothesis="Matrix updates may want a slightly different global pace under this budget.",
            rationale="Matrix LR changes the dominant optimization path without changing architecture.",
        ),
        SearchKnob(
            path="optimizer_groups.scalar_lr_scale",
            values=(0.85, 1.15),
            tag="scalar_lr",
            hypothesis="Scalar policies can converge better with their own LR balance.",
            rationale="Scalar LR supports x0/residual-style tuning without touching code.",
        ),
        SearchKnob(
            path="optimizer_groups.weight_decay",
            values=(0.12, 0.18, 0.24),
            tag="weight_decay",
            hypothesis="Regularization may be slightly mis-tuned for this campaign budget.",
            rationale="Weight decay remains a high-value single-knob ablation and combine ingredient.",
        ),
        SearchKnob(
            path="schedule.warmdown_ratio",
            values=(0.35, 0.50, 0.65),
            tag="warmdown",
            hypothesis="The tail of the run may need a different anneal profile to cash out the budget.",
            rationale="Warmdown is a required structured optimization knob in v1.",
        ),
        SearchKnob(
            path="model.rope_base",
            values=(10_000, 20_000, 50_000),
            tag="rope_base",
            hypothesis="RoPE base may affect how quickly the model uses the available context.",
            rationale="RoPE base is a clean dense-model search knob with clear reportability.",
        ),
        SearchKnob(
            path="model.ema_at_eval",
            values=(True, False),
            tag="ema",
            hypothesis="EMA-at-eval may stabilize short-budget comparisons.",
            rationale="EMA is allowed in the structured search surface when it remains explicit and auditable.",
        ),
        SearchKnob(
            path="curriculum.sequence_curriculum.enabled",
            values=(True, False),
            tag="sequence_curriculum",
            hypothesis="Sequence curriculum may use a fixed budget more efficiently before full-context evaluation.",
            rationale="Sequence curriculum is a required v1 curriculum knob.",
        ),
        SearchKnob(
            path="curriculum.progressive_depth.enabled",
            values=(True, False),
            tag="progressive_depth",
            hypothesis="Progressive depth may let the model spend more early steps on cheap signal accumulation.",
            rationale="Progressive depth is a required v1 curriculum knob.",
        ),
    )

    if lane == "confirm":
        return tuple(
            knob
            for knob in knob_pool
            if knob.path
            in {
                "model.window_pattern",
                "optimizer_groups.embed_lr_scale",
                "optimizer_groups.unembed_lr_scale",
                "optimizer_groups.matrix_lr_scale",
                "optimizer_groups.scalar_lr_scale",
                "optimizer_groups.weight_decay",
                "schedule.warmdown_ratio",
                "model.ema_at_eval",
            }
        )
    return knob_pool


def legal_mutations(
    campaign: dict[str, Any],
    base_overrides: dict[str, Any],
    lane: str,
    *,
    device_profile: Any | None = None,
) -> list[tuple[SearchKnob, Any, dict[str, Any]]]:
    mutations: list[tuple[SearchKnob, Any, dict[str, Any]]] = []
    for knob in search_knobs_for_campaign(campaign, lane, device_profile=device_profile):
        for value in knob.values:
            overrides = apply_path_override(base_overrides, knob.path, value)
            resolved = resolve_dense_config(campaign, overrides, device_profile=device_profile)
            if validate_dense_config(campaign, resolved, device_profile=device_profile):
                continue
            mutations.append((knob, value, overrides))
    return mutations


__all__ = [
    "SearchKnob",
    "apply_path_override",
    "estimate_complexity_cost",
    "estimate_peak_vram_gb",
    "flatten_override_paths",
    "legal_mutations",
    "resolve_dense_config",
    "search_knobs_for_campaign",
    "validate_dense_config",
]
