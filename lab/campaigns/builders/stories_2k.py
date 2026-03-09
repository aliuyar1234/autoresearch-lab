from __future__ import annotations

from pathlib import Path

from reference_impl.campaign_split_rules import stories_split_for_document


def collect_split_documents(source_root: Path, campaign: dict[str, object]) -> dict[str, list[dict[str, str]]]:
    splits = {
        "train": [],
        "search_val": [],
        "audit_val": [],
        "locked_val": [],
    }
    for path in sorted(source_root.iterdir()):
        if not path.is_file():
            continue
        split = stories_split_for_document(path.name)
        splits[split].append({"doc_id": path.name, "text": path.read_text(encoding="utf-8")})
    return splits
