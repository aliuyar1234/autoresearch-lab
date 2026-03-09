from __future__ import annotations

from typing import Any

import torch


def build_optimizer(model, config: dict[str, Any]) -> torch.optim.Optimizer:
    groups = config["optimizer_groups"]
    embedding_params = []
    unembedding_params = []
    matrix_params = []
    scalar_params = []

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if name.startswith("token_embedding"):
            embedding_params.append(param)
        elif name.startswith("lm_head"):
            unembedding_params.append(param)
        elif param.ndim < 2:
            scalar_params.append(param)
        else:
            matrix_params.append(param)

    param_groups = [
        {
            "params": embedding_params,
            "lr": float(groups["embedding_lr"]) * float(groups["embed_lr_scale"]),
            "weight_decay": 0.0,
            "group_name": "embedding",
            "initial_lr": float(groups["embedding_lr"]) * float(groups["embed_lr_scale"]),
        },
        {
            "params": unembedding_params,
            "lr": float(groups["unembedding_lr"]) * float(groups["unembed_lr_scale"]),
            "weight_decay": 0.0,
            "group_name": "unembedding",
            "initial_lr": float(groups["unembedding_lr"]) * float(groups["unembed_lr_scale"]),
        },
        {
            "params": matrix_params,
            "lr": float(groups["matrix_lr"]) * float(groups["matrix_lr_scale"]),
            "weight_decay": float(groups["weight_decay"]),
            "group_name": "matrix",
            "initial_lr": float(groups["matrix_lr"]) * float(groups["matrix_lr_scale"]),
        },
        {
            "params": scalar_params,
            "lr": float(groups["scalar_lr"]) * float(groups["scalar_lr_scale"]),
            "weight_decay": 0.0,
            "group_name": "scalar",
            "initial_lr": float(groups["scalar_lr"]) * float(groups["scalar_lr_scale"]),
        },
    ]
    betas = tuple(float(item) for item in groups.get("adam_betas", [0.9, 0.95]))
    return torch.optim.AdamW(param_groups, betas=betas, eps=1e-8)


def lr_multiplier(progress: float, config: dict[str, Any]) -> float:
    schedule = config["schedule"]
    warmup_ratio = float(schedule.get("warmup_ratio", 0.0))
    warmdown_ratio = float(schedule.get("warmdown_ratio", 0.0))
    final_lr_fraction = float(schedule.get("final_lr_fraction", 0.0))
    if warmup_ratio > 0 and progress < warmup_ratio:
        return progress / max(warmup_ratio, 1e-9)
    if warmdown_ratio <= 0 or progress < 1.0 - warmdown_ratio:
        return 1.0
    remaining = max(0.0, 1.0 - progress)
    tail = remaining / max(warmdown_ratio, 1e-9)
    return (tail * 1.0) + ((1.0 - tail) * final_lr_fraction)


def apply_schedule(optimizer: torch.optim.Optimizer, progress: float, config: dict[str, Any]) -> None:
    multiplier = lr_multiplier(progress, config)
    weight_decay = float(config["optimizer_groups"]["weight_decay"])
    for group in optimizer.param_groups:
        group["lr"] = float(group["initial_lr"]) * multiplier
        if group["group_name"] == "matrix":
            group["weight_decay"] = weight_decay * max(0.0, 1.0 - progress)


def update_ema(shadow: dict[str, torch.Tensor], model, *, decay: float) -> None:
    with torch.no_grad():
        for name, param in model.named_parameters():
            if name not in shadow:
                shadow[name] = param.detach().clone()
                continue
            shadow[name].mul_(decay).add_(param.detach(), alpha=1.0 - decay)


__all__ = ["apply_schedule", "build_optimizer", "lr_multiplier", "update_ema"]
