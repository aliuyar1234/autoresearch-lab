from __future__ import annotations

import importlib
import importlib.util
import os
import pathlib
import site
import sysconfig
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DeviceProfile:
    profile_id: str
    device_name: str
    vendor: str
    family: str
    compute_capability: str | None
    vram_gb: int | None
    preferred_dtype: str
    supports_compile: bool
    supports_flash_attention: bool
    supports_flex_attention: bool
    safe_device_batch_ceiling: int
    supports_high_confirm_budget: bool
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _torch_module():
    try:
        return importlib.import_module("torch")
    except Exception:
        return None


def _supports_flex_attention() -> bool:
    try:
        return importlib.import_module("torch.nn.attention.flex_attention") is not None
    except Exception:
        return False


def _supports_flash_attention() -> bool:
    try:
        return importlib.import_module("kernels") is not None
    except Exception:
        return False


def bundled_triton_cuda_root() -> pathlib.Path | None:
    candidates: list[pathlib.Path] = []
    spec = importlib.util.find_spec("triton")
    if spec and spec.origin:
        candidates.append(pathlib.Path(spec.origin).resolve().parent / "backends" / "nvidia")
    for root in {
        pathlib.Path(sysconfig.get_paths()["platlib"]),
        pathlib.Path(sysconfig.get_paths()["purelib"]),
        pathlib.Path(site.getusersitepackages()),
        *[pathlib.Path(item) for item in site.getsitepackages()],
    }:
        candidates.append(root / "triton" / "backends" / "nvidia")
    for base in candidates:
        required = (
            base / "bin" / "ptxas.exe",
            base / "include" / "cuda.h",
            base / "lib" / "x64" / "cuda.lib",
        )
        if all(path.exists() for path in required):
            return base
    return None


def ensure_cuda_path_configured() -> str | None:
    existing = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
    if existing:
        os.environ.setdefault("CUDA_PATH", existing)
        os.environ.setdefault("CUDA_HOME", existing)
        return existing
    bundled = bundled_triton_cuda_root()
    if bundled is None:
        return None
    os.environ["CUDA_PATH"] = str(bundled)
    os.environ["CUDA_HOME"] = str(bundled)
    return str(bundled)


def named_device_profile(profile_id: str) -> DeviceProfile:
    if profile_id == "rtx_pro_6000_96gb":
        return DeviceProfile(
            profile_id="rtx_pro_6000_96gb",
            device_name="NVIDIA RTX PRO 6000 Blackwell",
            vendor="nvidia",
            family="blackwell",
            compute_capability="12.0",
            vram_gb=96,
            preferred_dtype="bfloat16",
            supports_compile=True,
            supports_flash_attention=_supports_flash_attention(),
            supports_flex_attention=_supports_flex_attention(),
            safe_device_batch_ceiling=256,
            supports_high_confirm_budget=True,
            notes=("target workstation profile",),
        )
    if profile_id == "generic_single_gpu_nvidia":
        return DeviceProfile(
            profile_id="generic_single_gpu_nvidia",
            device_name="Generic NVIDIA single GPU",
            vendor="nvidia",
            family="generic",
            compute_capability=None,
            vram_gb=None,
            preferred_dtype="bfloat16",
            supports_compile=True,
            supports_flash_attention=_supports_flash_attention(),
            supports_flex_attention=_supports_flex_attention(),
            safe_device_batch_ceiling=128,
            supports_high_confirm_budget=False,
            notes=("fallback NVIDIA profile",),
        )
    return DeviceProfile(
        profile_id=profile_id,
        device_name=profile_id,
        vendor="unknown",
        family="unknown",
        compute_capability=None,
        vram_gb=None,
        preferred_dtype="float32",
        supports_compile=False,
        supports_flash_attention=False,
        supports_flex_attention=False,
        safe_device_batch_ceiling=8,
        supports_high_confirm_budget=False,
        notes=("user-specified custom profile",),
    )


def detect_device_profile(profile_override: str | None = None) -> DeviceProfile:
    ensure_cuda_path_configured()
    if profile_override:
        return named_device_profile(profile_override)

    torch = _torch_module()
    if torch is None or not torch.cuda.is_available():
        return DeviceProfile(
            profile_id="cpu_only",
            device_name="CPU only",
            vendor="cpu",
            family="cpu",
            compute_capability=None,
            vram_gb=None,
            preferred_dtype="float32",
            supports_compile=False,
            supports_flash_attention=False,
            supports_flex_attention=False,
            safe_device_batch_ceiling=4,
            supports_high_confirm_budget=False,
            notes=("CUDA unavailable",),
        )

    properties = torch.cuda.get_device_properties(0)
    device_name = torch.cuda.get_device_name(0)
    compute_capability = f"{properties.major}.{properties.minor}"
    vram_gb = int(round(properties.total_memory / float(1024**3)))
    lowered = device_name.lower()

    if "rtx pro 6000" in lowered and vram_gb >= 90:
        profile = named_device_profile("rtx_pro_6000_96gb")
        return DeviceProfile(
            **{
                **profile.to_dict(),
                "device_name": device_name,
                "compute_capability": compute_capability,
                "vram_gb": vram_gb,
            }
        )

    return DeviceProfile(
        profile_id="generic_single_gpu_nvidia",
        device_name=device_name,
        vendor="nvidia",
        family="generic",
        compute_capability=compute_capability,
        vram_gb=vram_gb,
        preferred_dtype="bfloat16",
        supports_compile=True,
        supports_flash_attention=_supports_flash_attention(),
        supports_flex_attention=_supports_flex_attention(),
        safe_device_batch_ceiling=128 if (vram_gb or 0) >= 40 else 64,
        supports_high_confirm_budget=(vram_gb or 0) >= 48,
        notes=("autodetected fallback NVIDIA profile",),
    )


__all__ = [
    "DeviceProfile",
    "bundled_triton_cuda_root",
    "detect_device_profile",
    "ensure_cuda_path_configured",
    "named_device_profile",
]
