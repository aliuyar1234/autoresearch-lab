from __future__ import annotations

from pathlib import Path
from typing import Any

from .campaigns import build_campaign, load_campaign, verify_campaign
from .campaigns.split_rules import stories_split_for_document
from .paths import LabPaths


class SmokeAssetError(ValueError):
    pass


def build_smoke_source_documents(campaign: dict[str, Any]) -> dict[str, str]:
    builder_module = str(campaign["dataset"]["builder"])
    if builder_module.endswith("stories_2k"):
        return _stories_smoke_documents(campaign)
    if builder_module.endswith(("base_2k", "long_4k")):
        return _base_like_smoke_documents(campaign)
    raise SmokeAssetError(f"unsupported smoke asset builder: {builder_module}")


def ensure_smoke_campaign_assets(paths: LabPaths, campaign_id: str) -> dict[str, Any]:
    verification = verify_campaign(paths, campaign_id)
    if verification["ok"]:
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "built": False,
            "asset_root": verification["asset_root"],
        }

    campaign = load_campaign(paths, campaign_id)
    source_root = paths.artifacts_root / "smoke" / "raw" / campaign_id
    documents = build_smoke_source_documents(campaign)
    source_root.mkdir(parents=True, exist_ok=True)
    for existing in source_root.iterdir():
        if existing.is_file():
            existing.unlink()
    for name, text in documents.items():
        (source_root / name).write_text(text, encoding="utf-8")

    payload = build_campaign(paths, campaign_id, source_dir=source_root)
    return {
        **payload,
        "built": True,
        "source_root": str(source_root),
    }


def _base_like_smoke_documents(campaign: dict[str, Any]) -> dict[str, str]:
    documents = {
        "smoke_train_00001.txt": "smoke training example one\nsmoke training example two\n",
        "smoke_train_00002.txt": "smoke training example three\nsmoke training example four\n",
    }
    for split_name in ("locked_val", "audit_val", "search_val"):
        for index, shard in enumerate(campaign["splits"].get(split_name, {}).get("shards", []), start=1):
            documents[str(shard)] = f"{split_name} smoke example {index}\n"
    return documents


def _stories_smoke_documents(campaign: dict[str, Any]) -> dict[str, str]:
    required_splits = ["train", "search_val", "audit_val", "locked_val"]
    documents: dict[str, str] = {}
    seen: set[str] = set()
    for index in range(20_000):
        name = f"smoke_story_{index:05d}.txt"
        split_name = stories_split_for_document(name)
        if split_name not in required_splits or split_name in seen:
            continue
        documents[name] = f"{split_name} smoke example {index}\n"
        seen.add(split_name)
        if len(seen) == len(required_splits):
            break
    if seen != set(required_splits):
        missing = sorted(set(required_splits) - seen)
        raise SmokeAssetError(f"could not synthesize stories smoke documents for splits: {', '.join(missing)}")
    return documents


__all__ = ["SmokeAssetError", "build_smoke_source_documents", "ensure_smoke_campaign_assets"]
