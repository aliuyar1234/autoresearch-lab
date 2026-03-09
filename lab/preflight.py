from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .backends import (
    available_backend_candidates,
    backend_blacklist_path,
    backend_cache_path,
    detect_device_profile,
    ensure_cuda_path_configured,
    select_backend,
    shape_family_for_run,
)
from .campaigns.load import load_campaign
from .paths import LabPaths, resolve_managed_path
from .utils.fs import nearest_existing_parent
from .utils.json_io import read_json
from research.dense_gpt.search_space import resolve_dense_config

REQUIRED_IMPORTS = (
    "torch",
    "numpy",
    "pandas",
    "pyarrow",
    "requests",
    "rustbpe",
    "tiktoken",
)


@dataclass
class PreflightResult:
    ok: bool
    device: str | None
    cuda_version: str | None
    driver: str | None
    campaign_id: str | None
    device_profile: str | None = None
    missing_assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    import_checks: dict[str, bool] = field(default_factory=dict)
    backend_candidates: list[str] = field(default_factory=list)
    backend_cache_path: str | None = None
    backend_blacklist_path: str | None = None
    backend_selection: dict[str, object] | None = None
    disk_free_gb: float | None = None
    artifact_root_writable: bool = False
    repo_root: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _check_imports() -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    warnings: list[str] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
            checks[module_name] = True
        except Exception:
            checks[module_name] = False
            warnings.append(f"missing import: {module_name}")
    return checks, warnings


def _detect_driver_version() -> str | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    line = completed.stdout.strip().splitlines()
    return line[0].strip() if line else None


def _collect_device_info() -> tuple[str | None, str | None, str | None, list[str], list[str]]:
    warnings: list[str] = []
    device_name: str | None = None
    cuda_version: str | None = None
    profile_id: str | None = None

    try:
        torch = importlib.import_module("torch")
    except Exception:
        warnings.append("torch import unavailable; skipping CUDA checks")
        return device_name, cuda_version, profile_id, [], warnings

    cuda_version = getattr(torch.version, "cuda", None)
    profile = detect_device_profile()
    profile_id = profile.profile_id
    if not torch.cuda.is_available():
        warnings.append("CUDA is not available")
        return device_name, cuda_version, profile_id, [], warnings

    try:
        device_name = torch.cuda.get_device_name(0)
    except Exception:
        device_name = "cuda:0"
    candidates = [candidate.name for candidate in available_backend_candidates(profile)]
    if "kernels" not in candidates:
        warnings.append("kernels package unavailable")
    return device_name, cuda_version, profile_id, candidates, warnings


def _resolve_disk_usage_target(path: Path) -> Path:
    if path.exists():
        return path
    return nearest_existing_parent(path)


def _is_writable(path: Path) -> bool:
    target = _resolve_disk_usage_target(path)
    return os.access(target, os.W_OK)


def _campaign_manifest_path(paths: LabPaths, campaign_id: str) -> Path:
    return paths.campaigns_root / campaign_id / "campaign.json"


def _find_missing_assets(paths: LabPaths, campaign_id: str) -> list[str]:
    manifest_path = _campaign_manifest_path(paths, campaign_id)
    if not manifest_path.exists():
        return [str(manifest_path.relative_to(paths.repo_root))]

    manifest = read_json(manifest_path)
    assets = manifest.get("assets", {})
    asset_root = resolve_managed_path(paths, assets.get("root", paths.campaign_cache_root / campaign_id))

    expected_files = [
        assets.get("tokenizer_manifest"),
        assets.get("pretok_manifest"),
        assets.get("packed_manifest"),
    ]
    expected_files.extend(manifest.get("tokenizer", {}).get("artifact_files", []))

    missing = []
    for name in expected_files:
        if not name:
            continue
        candidate = asset_root / name
        if not candidate.exists():
            missing.append(str(candidate.relative_to(paths.repo_root)))
    return missing


def run_preflight(paths: LabPaths, campaign_id: str | None = None, *, benchmark_backends: bool = False) -> PreflightResult:
    ensure_cuda_path_configured()
    import_checks, warnings = _check_imports()
    device, cuda_version, device_profile, backend_candidates, device_warnings = _collect_device_info()
    warnings.extend(device_warnings)

    usage_target = _resolve_disk_usage_target(paths.artifacts_root)
    disk_free_gb = shutil.disk_usage(usage_target).free / (1024**3)
    writable = _is_writable(paths.artifacts_root)
    if not writable:
        warnings.append(f"artifacts root is not writable: {paths.artifacts_root}")

    missing_assets: list[str] = []
    if campaign_id:
        missing_assets.extend(_find_missing_assets(paths, campaign_id))

    if not paths.db_path.exists():
        warnings.append(f"database file does not exist yet: {paths.db_path}")

    backend_selection = None
    if benchmark_backends and campaign_id and device_profile and backend_candidates:
        try:
            campaign = load_campaign(paths, campaign_id)
            resolved = resolve_dense_config(campaign, {})
            profile = detect_device_profile(device_profile)
            backend_selection = select_backend(
                cache_path=backend_cache_path(paths),
                blacklist_path=backend_blacklist_path(paths),
                candidates=available_backend_candidates(profile),
                shape=shape_family_for_run(campaign, resolved, profile, purpose="train"),
                device_profile=profile,
                cuda_version=cuda_version,
                torch_version=_torch_version(),
                compile_enabled=bool(resolved["runtime"].get("compile_enabled", True)),
                force_rebenchmark=True,
            ).to_dict()
        except Exception as exc:
            warnings.append(f"backend benchmark failed: {exc}")

    ok = all(import_checks.values()) and writable and not missing_assets
    if campaign_id is None:
        ok = all(import_checks.values()) and writable

    return PreflightResult(
        ok=ok,
        device=device,
        cuda_version=cuda_version,
        driver=_detect_driver_version(),
        campaign_id=campaign_id,
        device_profile=device_profile,
        missing_assets=missing_assets,
        warnings=warnings,
        import_checks=import_checks,
        backend_candidates=backend_candidates,
        backend_cache_path=str(backend_cache_path(paths)),
        backend_blacklist_path=str(backend_blacklist_path(paths)),
        backend_selection=backend_selection,
        disk_free_gb=round(disk_free_gb, 2),
        artifact_root_writable=writable,
        repo_root=str(paths.repo_root),
    )


def _torch_version() -> str:
    try:
        torch = importlib.import_module("torch")
    except Exception:
        return "unavailable"
    return str(getattr(torch, "__version__", "unavailable"))
