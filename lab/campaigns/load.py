from __future__ import annotations

from pathlib import Path
from typing import Any

from ..paths import LabPaths, resolve_managed_path
from ..utils import load_schema, read_json, validate_payload


def list_campaigns(paths: LabPaths) -> list[dict[str, Any]]:
    campaigns: list[dict[str, Any]] = []
    if not paths.campaigns_root.exists():
        return campaigns
    for manifest_path in sorted(paths.campaigns_root.glob("*/campaign.json")):
        payload = load_campaign(paths, manifest_path.parent.name)
        campaigns.append(
            {
                "campaign_id": payload["campaign_id"],
                "title": payload["title"],
                "active": payload["active"],
                "sequence_length": payload["sequence_length"],
            }
        )
    return campaigns


def load_campaign(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    manifest_path = paths.campaigns_root / campaign_id / "campaign.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"campaign manifest not found: {manifest_path}")
    payload = read_json(manifest_path)
    validate_payload(payload, load_schema(paths.schemas_root / "campaign.schema.json"))
    return payload


def resolve_asset_root(paths: LabPaths, campaign: dict[str, Any]) -> Path:
    return resolve_managed_path(paths, campaign["assets"]["root"])


def resolve_raw_cache_root(paths: LabPaths, campaign: dict[str, Any], source_dir: str | Path | None = None) -> Path:
    if source_dir is not None:
        return Path(source_dir).resolve()
    return resolve_managed_path(paths, campaign["dataset"]["raw_cache_root"])
