from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from ..artifacts import build_artifact_record
from ..paths import LabPaths
from ..utils import read_json, sha256_file, utc_now_iso, write_json
from .load import load_campaign, resolve_asset_root, resolve_raw_cache_root
from .packing import pack_tokenized_documents, serialize_packed_blocks


class CampaignBuildError(ValueError):
    pass


def build_campaign(paths: LabPaths, campaign_id: str, *, source_dir: str | Path | None = None) -> dict[str, Any]:
    campaign = load_campaign(paths, campaign_id)
    asset_root = resolve_asset_root(paths, campaign)
    source_root = resolve_raw_cache_root(paths, campaign, source_dir)
    asset_root.mkdir(parents=True, exist_ok=True)

    builder = importlib.import_module(campaign["dataset"]["builder"])
    split_documents = builder.collect_split_documents(source_root, campaign)
    if not any(split_documents.values()):
        raise CampaignBuildError(f"no source documents found in {source_root}")

    raw_manifest_path = asset_root / "raw.manifest.json"
    raw_manifest = _build_raw_manifest(source_root)
    _write_manifest(raw_manifest_path, raw_manifest)

    tokenizer_manifest = _build_tokenizer_assets(asset_root, campaign)
    _write_manifest(asset_root / campaign["assets"]["tokenizer_manifest"], tokenizer_manifest)

    pretokenized_manifest = _build_pretokenized_assets(asset_root, campaign, split_documents)
    _write_manifest(asset_root / campaign["assets"]["pretok_manifest"], pretokenized_manifest)

    packed_manifest = _build_packed_assets(asset_root, campaign, pretokenized_manifest)
    _write_manifest(asset_root / campaign["assets"]["packed_manifest"], packed_manifest)

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "asset_root": str(asset_root),
        "raw_manifest": str(raw_manifest_path),
        "tokenizer_manifest": str(asset_root / campaign["assets"]["tokenizer_manifest"]),
        "pretok_manifest": str(asset_root / campaign["assets"]["pretok_manifest"]),
        "packed_manifest": str(asset_root / campaign["assets"]["packed_manifest"]),
    }


def _build_raw_manifest(source_root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(source_root.iterdir()):
        if path.is_file():
            files.append(
                {
                    "path": path.name,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    return {
        "created_at": utc_now_iso(),
        "source_root": str(source_root),
        "files": files,
    }


def _build_tokenizer_assets(asset_root: Path, campaign: dict[str, Any]) -> dict[str, Any]:
    artifact_files = campaign["tokenizer"]["artifact_files"]
    tokenizer_path = asset_root / artifact_files[0]
    merges_path = asset_root / artifact_files[1]
    meta_path = asset_root / artifact_files[2]

    tokenizer_payload = {
        "kind": "byte_fallback",
        "campaign_id": campaign["campaign_id"],
        "bos_token_id": 1,
        "pad_token_id": 0,
        "offset": 2,
        "vocab_size": campaign["tokenizer"]["vocab_size"],
    }
    write_json(tokenizer_path, tokenizer_payload)
    merges_path.write_text("# deterministic byte fallback tokenizer\n", encoding="utf-8")
    write_json(meta_path, tokenizer_payload)

    return {
        "created_at": utc_now_iso(),
        "campaign_id": campaign["campaign_id"],
        "files": [
            _file_entry(asset_root, artifact_files[0]),
            _file_entry(asset_root, artifact_files[1]),
            _file_entry(asset_root, artifact_files[2]),
        ],
    }


def _build_pretokenized_assets(asset_root: Path, campaign: dict[str, Any], split_documents: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    manifest_files = []
    for split_name, docs in split_documents.items():
        tokenized_docs = []
        for doc in docs:
            tokenized_docs.append(
                {
                    "doc_id": doc["doc_id"],
                    "tokens": _encode_text(doc["text"]),
                }
            )
        target_path = asset_root / f"pretok_{split_name}.json"
        target_path.write_text(json.dumps(tokenized_docs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_files.append(
            {
                **_file_entry(asset_root, target_path.name),
                "split": split_name,
                "document_count": len(tokenized_docs),
            }
        )
    return {
        "created_at": utc_now_iso(),
        "campaign_id": campaign["campaign_id"],
        "sequence_length": campaign["sequence_length"],
        "bos_token_id": 1,
        "files": manifest_files,
    }


def _build_packed_assets(asset_root: Path, campaign: dict[str, Any], pretokenized_manifest: dict[str, Any]) -> dict[str, Any]:
    packed_files = []
    for entry in pretokenized_manifest["files"]:
        pretok_path = asset_root / entry["path"]
        tokenized_docs = read_json(pretok_path)
        blocks = pack_tokenized_documents(
            (doc["tokens"] for doc in tokenized_docs),
            sequence_length=campaign["sequence_length"],
            bos_token_id=1,
        )
        packed_payload = serialize_packed_blocks(blocks)
        target_name = entry["path"].replace("pretok_", "packed_")
        target_path = asset_root / target_name
        target_path.write_text(json.dumps(packed_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        packed_files.append(
            {
                **_file_entry(asset_root, target_name),
                "split": entry["split"],
                "block_count": len(packed_payload),
                "padding_tokens": sum(block["padding_tokens"] for block in packed_payload),
            }
        )
    return {
        "created_at": utc_now_iso(),
        "campaign_id": campaign["campaign_id"],
        "sequence_length": campaign["sequence_length"],
        "files": packed_files,
    }


def _file_entry(asset_root: Path, filename: str) -> dict[str, Any]:
    path = asset_root / filename
    return {
        "path": filename,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _encode_text(text: str) -> list[int]:
    return [byte + 2 for byte in text.encode("utf-8")]


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        existing = read_json(path)
        if isinstance(existing, dict):
            comparable_existing = dict(existing)
            comparable_existing.pop("created_at", None)
            comparable_payload = dict(payload)
            comparable_payload.pop("created_at", None)
            if comparable_existing == comparable_payload:
                payload["created_at"] = existing.get("created_at", payload["created_at"])
    write_json(path, payload)
