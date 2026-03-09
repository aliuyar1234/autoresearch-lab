from __future__ import annotations

from pathlib import Path
from typing import Any

from ..paths import LabPaths
from ..utils import read_json, sha256_file
from .load import load_campaign, resolve_asset_root


def verify_campaign(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    campaign = load_campaign(paths, campaign_id)
    asset_root = resolve_asset_root(paths, campaign)
    problems: list[str] = []
    checked_files: list[str] = []

    manifest_names = [
        campaign["assets"]["tokenizer_manifest"],
        campaign["assets"]["pretok_manifest"],
        campaign["assets"]["packed_manifest"],
        "raw.manifest.json",
    ]
    for name in manifest_names:
        manifest_path = asset_root / name
        if not manifest_path.exists():
            problems.append(f"missing manifest: {manifest_path}")
            continue
        checked_files.append(str(manifest_path))
        manifest_payload = read_json(manifest_path)
        file_root = _resolve_manifest_file_root(asset_root, name, manifest_payload)
        for entry in manifest_payload.get("files", []):
            file_path = file_root / entry["path"]
            if not file_path.exists():
                problems.append(f"missing asset file: {file_path}")
                continue
            checked_files.append(str(file_path))
            actual_hash = sha256_file(file_path)
            if actual_hash != entry["sha256"]:
                problems.append(f"hash mismatch for {file_path}")
    return {
        "ok": not problems,
        "campaign_id": campaign_id,
        "asset_root": str(asset_root),
        "checked_files": checked_files,
        "problems": problems,
    }


def _resolve_manifest_file_root(asset_root: Path, manifest_name: str, manifest_payload: dict[str, Any]) -> Path:
    if manifest_name != "raw.manifest.json":
        return asset_root
    source_root = manifest_payload.get("source_root")
    if not isinstance(source_root, str) or not source_root:
        return asset_root
    return Path(source_root)
