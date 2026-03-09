from __future__ import annotations

from pathlib import Path


def collect_split_documents(source_root: Path, campaign: dict[str, object]) -> dict[str, list[dict[str, str]]]:
    splits = {
        "train": [],
        "search_val": [],
        "audit_val": [],
        "locked_val": [],
    }
    search_shards = set(campaign["splits"]["search_val"]["shards"])
    audit_shards = set(campaign["splits"]["audit_val"]["shards"])
    locked_shards = set(campaign["splits"].get("locked_val", {}).get("shards", []))
    excluded = set(campaign["splits"]["train"].get("exclude_shards", []))

    for path in sorted(source_root.iterdir()):
        if not path.is_file():
            continue
        payload = {"doc_id": path.name, "text": path.read_text(encoding="utf-8")}
        if path.name in search_shards:
            splits["search_val"].append(payload)
        elif path.name in audit_shards:
            splits["audit_val"].append(payload)
        elif path.name in locked_shards:
            splits["locked_val"].append(payload)
        elif path.name not in excluded:
            splits["train"].append(payload)
    return splits
