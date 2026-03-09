from __future__ import annotations

from pathlib import Path

from .base_2k import collect_split_documents as collect_base_like_documents


def collect_split_documents(source_root: Path, campaign: dict[str, object]) -> dict[str, list[dict[str, str]]]:
    return collect_base_like_documents(source_root, campaign)
