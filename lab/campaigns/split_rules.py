from __future__ import annotations


STORIES_PARTITION_MODULUS = 1000
STORIES_SEARCH_PARTITION = 999
STORIES_AUDIT_PARTITION = 998
STORIES_LOCKED_PARTITION = 997
STORIES_SEED = 1337


def stories_partition_for_document(
    doc_key: str,
    *,
    seed: int = STORIES_SEED,
    modulus: int = STORIES_PARTITION_MODULUS,
) -> int:
    total = seed
    for char in doc_key:
        total = (total * 131 + ord(char)) % 2_147_483_647
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
