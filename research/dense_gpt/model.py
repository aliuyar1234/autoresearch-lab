from __future__ import annotations

import importlib
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class DenseGPTConfig:
    vocab_size: int
    sequence_length: int
    depth: int
    n_embd: int
    n_head: int
    n_kv_head: int
    head_dim: int
    window_pattern: str
    rope_base: int
    backend: str

    @classmethod
    def from_resolved_config(cls, config: dict[str, object], *, backend: str) -> "DenseGPTConfig":
        resolved = config["resolved"]
        model = config["model"]
        return cls(
            vocab_size=int(resolved["vocab_size"]),
            sequence_length=int(resolved["sequence_length"]),
            depth=int(model["depth"]),
            n_embd=int(resolved["n_embd"]),
            n_head=int(resolved["n_head"]),
            n_kv_head=int(resolved["n_kv_head"]),
            head_dim=int(resolved["head_dim"]),
            window_pattern=str(model["window_pattern"]).upper(),
            rope_base=int(model["rope_base"]),
            backend=backend,
        )


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat((-x2, x1), dim=-1)


def _apply_rotary(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    return (x * cos) + (_rotate_half(x) * sin)


class CausalSelfAttention(nn.Module):
    def __init__(self, config: DenseGPTConfig, layer_idx: int) -> None:
        super().__init__()
        self.config = config
        self.layer_idx = layer_idx
        self.window_char = config.window_pattern[layer_idx % len(config.window_pattern)]
        self.q_proj = nn.Linear(config.n_embd, config.n_head * config.head_dim, bias=False)
        self.k_proj = nn.Linear(config.n_embd, config.n_kv_head * config.head_dim, bias=False)
        self.v_proj = nn.Linear(config.n_embd, config.n_kv_head * config.head_dim, bias=False)
        self.out_proj = nn.Linear(config.n_embd, config.n_embd, bias=False)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        batch, seq_len, _ = x.shape
        q = self.q_proj(x).view(batch, seq_len, self.config.n_head, self.config.head_dim)
        k = self.k_proj(x).view(batch, seq_len, self.config.n_kv_head, self.config.head_dim)
        v = self.v_proj(x).view(batch, seq_len, self.config.n_kv_head, self.config.head_dim)
        q = _apply_rotary(q, cos, sin)
        k = _apply_rotary(k, cos, sin)
        attn_out = self._attention(q, k, v, seq_len)
        return self.out_proj(attn_out.reshape(batch, seq_len, self.config.n_embd))

    def _attention(self, q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, seq_len: int) -> torch.Tensor:
        if self.config.backend == "kernels":
            return self._flash_attention(q, k, v, seq_len)
        if self.config.backend == "flex_attention":
            raise RuntimeError("unsupported backend: flex_attention")
        return self._sdpa_attention(q, k, v, seq_len)

    def _sdpa_attention(self, q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, seq_len: int) -> torch.Tensor:
        q_heads = q.transpose(1, 2)
        k_heads = k.transpose(1, 2)
        v_heads = v.transpose(1, 2)
        if self.config.n_head != self.config.n_kv_head:
            factor = self.config.n_head // self.config.n_kv_head
            k_heads = k_heads.repeat_interleave(factor, dim=1)
            v_heads = v_heads.repeat_interleave(factor, dim=1)
        if self.window_char == "L":
            out = F.scaled_dot_product_attention(q_heads, k_heads, v_heads, is_causal=True)
        else:
            window = max(1, seq_len // 2)
            mask = _local_causal_mask(seq_len, window, device=q.device)
            out = F.scaled_dot_product_attention(q_heads, k_heads, v_heads, attn_mask=mask, is_causal=False)
        return out.transpose(1, 2)

    def _flash_attention(self, q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, seq_len: int) -> torch.Tensor:
        kernels = importlib.import_module("kernels")
        capability = torch.cuda.get_device_capability()
        repo = "varunneal/flash-attention-3" if capability == (9, 0) else "kernels-community/flash-attn3"
        flash_attn = kernels.get_kernel(repo).flash_attn_interface.flash_attn_func
        window = (-1, -1) if self.window_char == "L" else (max(1, seq_len // 2), 0)
        return flash_attn(q, k, v, causal=True, window_size=window)


class Block(nn.Module):
    def __init__(self, config: DenseGPTConfig, layer_idx: int) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd)
        self.ln2 = nn.LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config, layer_idx)
        self.mlp = nn.Sequential(
            nn.Linear(config.n_embd, 4 * config.n_embd, bias=False),
            nn.GELU(),
            nn.Linear(4 * config.n_embd, config.n_embd, bias=False),
        )

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), cos, sin)
        x = x + self.mlp(self.ln2(x))
        return x


class DenseGPT(nn.Module):
    def __init__(self, config: DenseGPTConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.n_embd)
        self.blocks = nn.ModuleList([Block(config, layer_idx) for layer_idx in range(config.depth)])
        self.final_norm = nn.LayerNorm(config.n_embd)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

    def forward(self, input_ids: torch.Tensor, targets: torch.Tensor | None = None, *, active_depth: int | None = None) -> torch.Tensor:
        x = self.token_embedding(input_ids)
        cos, sin = rotary_cache(
            input_ids.size(1),
            self.config.head_dim,
            base=self.config.rope_base,
            device=input_ids.device,
            dtype=x.dtype,
        )
        use_depth = active_depth if active_depth is not None else self.config.depth
        for block in self.blocks[:use_depth]:
            x = block(x, cos, sin)
        x = self.final_norm(x)
        logits = self.lm_head(x)
        if targets is None:
            return logits
        return F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))

    def parameter_count(self) -> int:
        return sum(param.numel() for param in self.parameters())


def rotary_cache(sequence_length: int, head_dim: int, *, base: int, device: torch.device, dtype: torch.dtype) -> tuple[torch.Tensor, torch.Tensor]:
    half_dim = head_dim // 2
    positions = torch.arange(sequence_length, device=device, dtype=torch.float32)
    freqs = torch.arange(half_dim, device=device, dtype=torch.float32)
    inv_freq = 1.0 / (base ** (freqs / max(1, half_dim)))
    angles = torch.outer(positions, inv_freq)
    cos = torch.cos(angles).to(dtype=dtype)
    sin = torch.sin(angles).to(dtype=dtype)
    cos = torch.stack([cos, cos], dim=-1).reshape(1, sequence_length, 1, head_dim)
    sin = torch.stack([sin, sin], dim=-1).reshape(1, sequence_length, 1, head_dim)
    return cos, sin


def _local_causal_mask(sequence_length: int, window: int, *, device: torch.device) -> torch.Tensor:
    positions = torch.arange(sequence_length, device=device)
    distance = positions[:, None] - positions[None, :]
    return (distance >= 0) & (distance < window)


def estimate_flops(config: DenseGPTConfig) -> int:
    width = config.n_embd
    return int(12 * config.depth * config.sequence_length * width * width)


__all__ = ["DenseGPT", "DenseGPTConfig", "estimate_flops"]
