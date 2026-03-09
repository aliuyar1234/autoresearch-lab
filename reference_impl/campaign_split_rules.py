from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


BASE_2K_SEARCH_VAL_SHARDS = ("shard_06542.parquet",)
BASE_2K_AUDIT_VAL_SHARDS = ("shard_06541.parquet",)
BASE_2K_LOCKED_VAL_SHARDS = ("shard_06540.parquet",)
BASE_2K_EXCLUDED_FROM_TRAIN = tuple(
    sorted(set(BASE_2K_SEARCH_VAL_SHARDS + BASE_2K_AUDIT_VAL_SHARDS + BASE_2K_LOCKED_VAL_SHARDS))
)

STORIES_PARTITION_MODULUS = 1000
STORIES_SEARCH_PARTITION = 999
STORIES_AUDIT_PARTITION = 998
STORIES_LOCKED_PARTITION = 997
STORIES_SEED = 1337


@dataclass(frozen=True)
class Base2KSplitRule:
    train_exclude_shards: tuple[str, ...] = BASE_2K_EXCLUDED_FROM_TRAIN
    search_val_shards: tuple[str, ...] = BASE_2K_SEARCH_VAL_SHARDS
    audit_val_shards: tuple[str, ...] = BASE_2K_AUDIT_VAL_SHARDS
    locked_val_shards: tuple[str, ...] = BASE_2K_LOCKED_VAL_SHARDS


def base_2k_train_filter(shard_name: str) -> bool:
    return shard_name not in BASE_2K_EXCLUDED_FROM_TRAIN


def stories_partition_for_document(doc_key: str, *, seed: int = STORIES_SEED, modulus: int = STORIES_PARTITION_MODULUS) -> int:
    # Stable small hash that does not depend on Python's salted hash().
    total = seed
    for ch in doc_key:
        total = (total * 131 + ord(ch)) % 2_147_483_647
    return total % modulus


def stories_split_for_document(doc_key: str) -> str:
    part = stories_partition_for_document(doc_key)
    if part == STORIES_SEARCH_PARTITION:
        return "search_val"
    if part == STORIES_AUDIT_PARTITION:
        return "audit_val"
    if part == STORIES_LOCKED_PARTITION:
        return "locked_val"
    return "train"
