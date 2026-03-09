from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import torch

from lab.backends import ensure_cuda_path_configured
from lab.campaigns.load import load_campaign, resolve_asset_root
from lab.paths import build_paths
from lab.settings import load_settings
from lab.utils import read_json, write_json

from .fingerprint import short_fingerprint
from .model import DenseGPT, DenseGPTConfig, estimate_flops
from .optim import apply_schedule, build_optimizer, update_ema


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tiny dense GPT trainer for Autoresearch Lab")
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--backend", default="sdpa")
    parser.add_argument("--device-profile", default="generic_single_gpu_nvidia")
    parser.add_argument("--repo-root")
    parser.add_argument("--artifacts-root")
    parser.add_argument("--cache-root")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--time-budget-seconds", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--eval-batches", type=int, default=2)
    parser.add_argument("--tiny", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = time.time()
    configured_cuda_path = ensure_cuda_path_configured()

    if args.require_cuda and not torch.cuda.is_available():
        raise RuntimeError("backend unavailable: CUDA is required for this tiny run")

    if args.seed is not None:
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed)
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config = read_json(Path(args.config_path))
    runtime = config["runtime"]
    warnings: list[str] = []
    if runtime.get("detected_device_profile") and runtime["detected_device_profile"] != args.device_profile:
        warnings.append(
            f"config was fingerprinted under {runtime['detected_device_profile']} but run is using {args.device_profile}"
        )

    device_batch_size = int(runtime["device_batch_size"])
    if args.tiny:
        device_batch_size = min(device_batch_size, 8)
    if device.type == "cpu":
        device_batch_size = min(device_batch_size, 4)

    effective_eval_batch_size = min(int(runtime.get("eval_batch_size", max(1, device_batch_size // 2))), device_batch_size)
    runtime["effective_device_batch_size"] = device_batch_size
    runtime["effective_eval_batch_size"] = effective_eval_batch_size

    dtype = _autocast_dtype(str(runtime.get("preferred_dtype", "bfloat16")), device)
    settings = load_settings(
        repo_root=args.repo_root or os.environ.get("LAB_REPO_ROOT"),
        artifacts_root=args.artifacts_root or os.environ.get("LAB_ARTIFACTS_ROOT"),
        cache_root=args.cache_root or os.environ.get("LAB_CACHE_ROOT"),
        env=os.environ,
    )
    paths = build_paths(settings)
    campaign = load_campaign(paths, args.campaign_id)

    train_blocks, eval_blocks = _load_blocks(paths, campaign, tiny=args.tiny)

    config_hash = short_fingerprint(config)
    model_config = DenseGPTConfig.from_resolved_config(config, backend=args.backend)
    model = DenseGPT(model_config).to(device)
    run_model = model

    compile_seconds = 0.0
    compile_requested = device.type == "cuda" and bool(runtime.get("compile_enabled")) and args.backend == "sdpa" and hasattr(torch, "compile")
    if compile_requested:
        compile_start = time.perf_counter()
        run_model = torch.compile(model, dynamic=False)
        compile_seconds = time.perf_counter() - compile_start

    optimizer = build_optimizer(model, config)
    ema_shadow: dict[str, torch.Tensor] = {}
    use_ema = bool(config["model"].get("ema_at_eval"))
    ema_decay = float(config["optimizer_groups"].get("ema_decay", 0.999))
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    autocast_enabled = device.type == "cuda"
    budget_start = time.perf_counter()
    train_seconds = 0.0
    tokens_processed = 0
    step = 0
    max_steps = int(args.max_steps) if int(args.max_steps) > 0 else (4 if args.tiny else 128)
    min_steps = min(4, max_steps)
    flops_per_step = estimate_flops(model_config) * device_batch_size

    while step < max_steps:
        if step >= min_steps and (time.perf_counter() - budget_start) >= float(args.time_budget_seconds):
            break

        x, y = _next_batch(train_blocks, batch_size=device_batch_size, device=device)
        x, y = _maybe_apply_curriculum(x, y, config, step=step, max_steps=max_steps)
        progress = step / max(1, max_steps - 1)
        active_depth = _active_depth(config, step=step, max_steps=max_steps)

        iter_start = time.perf_counter()
        with torch.autocast(device_type=device.type, dtype=dtype, enabled=autocast_enabled):
            loss = run_model(x, y, active_depth=active_depth)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        apply_schedule(optimizer, progress, config)
        if use_ema:
            update_ema(ema_shadow, model, decay=ema_decay)
        if device.type == "cuda":
            torch.cuda.synchronize()
        train_seconds += time.perf_counter() - iter_start
        tokens_processed += int(x.numel())
        step += 1

    checkpoint_path = os.environ.get("LAB_PRE_EVAL_CHECKPOINT_PATH")
    checkpoint_meta_path = os.environ.get("LAB_PRE_EVAL_META_PATH")
    if checkpoint_path and checkpoint_meta_path:
        _write_checkpoint(Path(checkpoint_path), Path(checkpoint_meta_path), model, args, config_hash)

    eval_start = time.perf_counter()
    primary_metric_value = _evaluate_bpb(
        run_model,
        eval_blocks,
        batch_size=effective_eval_batch_size,
        device=device,
        eval_batches=max(1, int(args.eval_batches)),
        config=config,
        ema_shadow=ema_shadow if use_ema else None,
    )
    if device.type == "cuda":
        torch.cuda.synchronize()
    eval_seconds = time.perf_counter() - eval_start

    total_seconds = time.time() - started_at
    tokens_per_second = 0.0 if train_seconds <= 0 else tokens_processed / train_seconds
    peak_vram_gb = (
        0.0 if device.type != "cuda" else torch.cuda.max_memory_allocated() / float(1024**3)
    )
    steady_state_mfu = None
    if device.type == "cuda" and train_seconds > 0:
        flops_per_second = flops_per_step * max(step, 1) / train_seconds
        steady_state_mfu = round(flops_per_second / 1.0e14, 4)

    payload = {
        "experiment_id": args.experiment_id,
        "proposal_id": args.proposal_id,
        "campaign_id": args.campaign_id,
        "lane": args.lane,
        "status": "completed",
        "primary_metric_name": campaign["primary_metric"]["name"],
        "primary_metric_value": primary_metric_value,
        "budget_seconds": int(args.time_budget_seconds),
        "train_seconds": round(train_seconds, 6),
        "eval_seconds": round(eval_seconds, 6),
        "compile_seconds": round(compile_seconds, 6),
        "tokens_processed": tokens_processed,
        "tokens_per_second": round(tokens_per_second, 6),
        "steady_state_mfu": steady_state_mfu,
        "peak_vram_gb": round(peak_vram_gb, 6),
        "param_count": model.parameter_count(),
        "backend": args.backend,
        "device_profile": args.device_profile,
        "seed": args.seed,
        "config_fingerprint": config_hash,
        "git_commit": os.environ.get("LAB_PARENT_COMMIT", "unknown"),
        "warnings": warnings,
        "checkpoint_path": checkpoint_path if checkpoint_path and Path(checkpoint_path).exists() else None,
        "summary_version": "1.0.0",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data_mode": "campaign_assets",
        "effective_device_batch_size": device_batch_size,
        "effective_eval_batch_size": effective_eval_batch_size,
        "total_seconds": round(total_seconds, 6),
    }
    write_json(summary_path, payload)
    return 0


def _load_blocks(paths, campaign: dict[str, Any], *, tiny: bool) -> tuple[list[list[int]], list[list[int]]]:
    asset_root = resolve_asset_root(paths, campaign)
    packed_manifest_path = asset_root / campaign["assets"]["packed_manifest"]
    if not packed_manifest_path.exists():
        raise FileNotFoundError(f"missing packed campaign manifest: {packed_manifest_path}")
    manifest = read_json(packed_manifest_path)
    train_files = [entry for entry in manifest.get("files", []) if entry.get("split") == "train"]
    eval_files = [entry for entry in manifest.get("files", []) if entry.get("split") in {"search_val", "audit_val", "locked_val"}]
    if not train_files or not eval_files:
        raise RuntimeError(f"campaign packed manifest is missing required train/eval splits: {packed_manifest_path}")
    train_blocks = _read_block_files(asset_root, train_files, max_blocks=512 if tiny else 2048)
    eval_blocks = _read_block_files(asset_root, eval_files, max_blocks=64 if tiny else 256)
    if not train_blocks or not eval_blocks:
        raise RuntimeError(f"campaign packed assets did not contain usable token blocks: {packed_manifest_path}")
    return train_blocks, eval_blocks


def _read_block_files(asset_root: Path, entries: list[dict[str, Any]], *, max_blocks: int) -> list[list[int]]:
    blocks: list[list[int]] = []
    for entry in entries:
        payload = read_json(asset_root / entry["path"])
        for block in payload:
            tokens = list(block.get("tokens", []))
            if len(tokens) >= 2:
                blocks.append(tokens)
            if len(blocks) >= max_blocks:
                return blocks
    return blocks


def _next_batch(blocks: list[list[int]], *, batch_size: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    samples = random.sample(blocks, k=min(batch_size, len(blocks)))
    x = torch.tensor([row[:-1] for row in samples], dtype=torch.long, device=device)
    y = torch.tensor([row[1:] for row in samples], dtype=torch.long, device=device)
    return x, y


def _maybe_apply_curriculum(x: torch.Tensor, y: torch.Tensor, config: dict[str, Any], *, step: int, max_steps: int) -> tuple[torch.Tensor, torch.Tensor]:
    curriculum = config["curriculum"]["sequence_curriculum"]
    if not bool(curriculum["enabled"]):
        return x, y
    progress = step / max(1, max_steps - 1)
    if progress >= 0.5:
        return x, y
    fraction = float(curriculum.get("start_fraction", 0.5))
    target_length = max(16, int(x.size(1) * fraction))
    return x[:, :target_length], y[:, :target_length]


def _active_depth(config: dict[str, Any], *, step: int, max_steps: int) -> int | None:
    progressive = config["curriculum"]["progressive_depth"]
    if not bool(progressive["enabled"]):
        return None
    warmup_fraction = float(progressive.get("warmup_fraction", 0.45))
    progress = step / max(1, max_steps - 1)
    if progress >= warmup_fraction:
        return None
    min_depth = int(progressive.get("min_depth", 4))
    return max(1, min(min_depth, int(config["model"]["depth"])))


def _evaluate_bpb(
    model,
    eval_blocks: list[list[int]],
    *,
    batch_size: int,
    device: torch.device,
    eval_batches: int,
    config: dict[str, Any],
    ema_shadow: dict[str, torch.Tensor] | None,
) -> float:
    backup = None
    if ema_shadow:
        backup = {name: param.detach().clone() for name, param in model.named_parameters()}
        with torch.no_grad():
            for name, param in model.named_parameters():
                param.copy_(ema_shadow[name])
    model.eval()
    total_nats = 0.0
    total_bytes = 0
    with torch.no_grad():
        for _ in range(eval_batches):
            x, y = _next_batch(eval_blocks, batch_size=batch_size, device=device)
            logits = model(x)
            loss_flat = torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                y.reshape(-1),
                reduction="none",
            )
            mask = (y.reshape(-1) > 1).to(loss_flat.dtype)
            total_nats += float((loss_flat * mask).sum().item())
            total_bytes += int(mask.sum().item())
    model.train()
    if backup is not None:
        with torch.no_grad():
            for name, param in model.named_parameters():
                param.copy_(backup[name])
    return round(total_nats / max(math.log(2) * max(total_bytes, 1), 1e-9), 6)


def _write_checkpoint(checkpoint_path: Path, checkpoint_meta_path: Path, model, args: argparse.Namespace, config_hash: str) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict()}, checkpoint_path)
    checkpoint_meta_path.write_text(
        json.dumps(
            {
                "experiment_id": args.experiment_id,
                "proposal_id": args.proposal_id,
                "campaign_id": args.campaign_id,
                "lane": args.lane,
                "backend": args.backend,
                "device_profile": args.device_profile,
                "config_fingerprint": config_hash,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _autocast_dtype(preferred_dtype: str, device: torch.device) -> torch.dtype:
    if device.type != "cuda":
        return torch.float32
    if preferred_dtype == "float16":
        return torch.float16
    if preferred_dtype == "float32":
        return torch.float32
    return torch.bfloat16


if __name__ == "__main__":
    raise SystemExit(main())
