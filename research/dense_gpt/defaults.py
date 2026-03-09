from __future__ import annotations

import copy
from typing import Any


PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "base_2k": {
        "model": {
            "depth": 8,
            "aspect_ratio": 64,
            "head_dim": 128,
            "kv_head_ratio": "full",
            "window_pattern": "SSSL",
            "rope_base": 10_000,
            "ema_at_eval": False,
        },
        "optimizer_groups": {
            "embedding_lr": 0.60,
            "unembedding_lr": 0.004,
            "matrix_lr": 0.040,
            "scalar_lr": 0.50,
            "embed_lr_scale": 1.0,
            "unembed_lr_scale": 1.0,
            "matrix_lr_scale": 1.0,
            "scalar_lr_scale": 1.0,
            "weight_decay": 0.20,
            "adam_betas": [0.8, 0.95],
            "ema_decay": 0.999,
        },
        "schedule": {
            "warmup_ratio": 0.00,
            "warmdown_ratio": 0.50,
            "final_lr_fraction": 0.00,
        },
        "curriculum": {
            "sequence_curriculum": {
                "enabled": False,
                "start_fraction": 0.50,
            },
            "progressive_depth": {
                "enabled": False,
                "warmup_fraction": 0.45,
                "min_depth": 4,
            },
        },
        "runtime": {
            "preferred_dtype": "bfloat16",
            "compile_enabled": True,
            "device_batch_size": 128,
            "eval_batch_size": 64,
        },
    },
    "stories_2k": {
        "model": {
            "depth": 6,
            "aspect_ratio": 64,
            "head_dim": 64,
            "kv_head_ratio": "full",
            "window_pattern": "SSLL",
            "rope_base": 10_000,
            "ema_at_eval": False,
        },
        "optimizer_groups": {
            "embedding_lr": 0.50,
            "unembedding_lr": 0.006,
            "matrix_lr": 0.035,
            "scalar_lr": 0.45,
            "embed_lr_scale": 1.0,
            "unembed_lr_scale": 1.0,
            "matrix_lr_scale": 1.0,
            "scalar_lr_scale": 1.0,
            "weight_decay": 0.16,
            "adam_betas": [0.8, 0.95],
            "ema_decay": 0.999,
        },
        "schedule": {
            "warmup_ratio": 0.00,
            "warmdown_ratio": 0.45,
            "final_lr_fraction": 0.00,
        },
        "curriculum": {
            "sequence_curriculum": {
                "enabled": False,
                "start_fraction": 0.50,
            },
            "progressive_depth": {
                "enabled": False,
                "warmup_fraction": 0.40,
                "min_depth": 4,
            },
        },
        "runtime": {
            "preferred_dtype": "bfloat16",
            "compile_enabled": True,
            "device_batch_size": 160,
            "eval_batch_size": 80,
        },
    },
    "long_4k": {
        "model": {
            "depth": 8,
            "aspect_ratio": 80,
            "head_dim": 128,
            "kv_head_ratio": "half",
            "window_pattern": "LLSL",
            "rope_base": 20_000,
            "ema_at_eval": True,
        },
        "optimizer_groups": {
            "embedding_lr": 0.48,
            "unembedding_lr": 0.004,
            "matrix_lr": 0.032,
            "scalar_lr": 0.42,
            "embed_lr_scale": 1.0,
            "unembed_lr_scale": 1.0,
            "matrix_lr_scale": 1.0,
            "scalar_lr_scale": 1.0,
            "weight_decay": 0.18,
            "adam_betas": [0.8, 0.95],
            "ema_decay": 0.9993,
        },
        "schedule": {
            "warmup_ratio": 0.00,
            "warmdown_ratio": 0.55,
            "final_lr_fraction": 0.00,
        },
        "curriculum": {
            "sequence_curriculum": {
                "enabled": True,
                "start_fraction": 0.50,
            },
            "progressive_depth": {
                "enabled": False,
                "warmup_fraction": 0.50,
                "min_depth": 4,
            },
        },
        "runtime": {
            "preferred_dtype": "bfloat16",
            "compile_enabled": True,
            "device_batch_size": 64,
            "eval_batch_size": 32,
        },
    },
}


def campaign_profile_name(campaign: dict[str, Any]) -> str:
    return str(campaign.get("search_space", {}).get("profile") or campaign["campaign_id"])


def profile_defaults(profile_name: str) -> dict[str, Any]:
    base = PROFILE_DEFAULTS.get(profile_name, PROFILE_DEFAULTS["base_2k"])
    return copy.deepcopy(base)


def base_config_for_campaign(campaign: dict[str, Any], *, device_profile: Any | None = None) -> dict[str, Any]:
    config = profile_defaults(campaign_profile_name(campaign))
    config["campaign"] = {
        "campaign_id": campaign["campaign_id"],
        "sequence_length": int(campaign["sequence_length"]),
        "vocab_size": int(campaign["vocab_size"]),
        "primary_metric_name": str(campaign["primary_metric"]["name"]),
        "primary_metric_direction": str(campaign["primary_metric"]["direction"]),
    }
    runtime = config.setdefault("runtime", {})
    runtime["preferred_dtype"] = str(campaign["runtime"].get("preferred_dtype", runtime.get("preferred_dtype", "bfloat16")))
    runtime["allowed_device_profiles"] = list(campaign["runtime"].get("allowed_device_profiles", []))
    runtime["backend_policy"] = str(campaign["runtime"].get("backend_policy", "benchmark_and_cache"))
    runtime["compile_cache_policy"] = str(campaign["runtime"].get("compile_cache_policy", "by_device_profile+shape_family+backend"))
    runtime["max_peak_vram_gb"] = float(campaign["runtime"].get("max_peak_vram_gb", 0.0) or 0.0)
    if device_profile is not None:
        runtime.setdefault("detected_device_profile", getattr(device_profile, "profile_id", None))
    return config
