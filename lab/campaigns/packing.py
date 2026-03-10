from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class PackedBlock:
    tokens: list[int]
    padding_tokens: int
    chunk_lengths: list[int]


def pack_tokenized_documents(
    tokenized_documents: Iterable[Sequence[int]],
    *,
    sequence_length: int,
    bos_token_id: int = 1,
) -> list[PackedBlock]:
    chunks = prepare_chunks(
        tokenized_documents,
        sequence_length=sequence_length,
        bos_token_id=bos_token_id,
    )
    return pack_chunks_best_fit(chunks, sequence_length)


def serialize_packed_blocks(blocks: Iterable[PackedBlock]) -> list[dict[str, object]]:
    return [
        {
            "tokens": block.tokens,
            "padding_tokens": block.padding_tokens,
            "chunk_lengths": block.chunk_lengths,
        }
        for block in blocks
    ]


def chunk_document(tokens: Sequence[int], max_len: int) -> list[list[int]]:
    if max_len <= 0:
        raise ValueError("max_len must be > 0")
    return [list(tokens[index : index + max_len]) for index in range(0, len(tokens), max_len)]


def prepare_chunks(
    tokenized_documents: Iterable[Sequence[int]],
    *,
    sequence_length: int,
    bos_token_id: int | None = None,
) -> list[list[int]]:
    chunks: list[list[int]] = []
    for document in tokenized_documents:
        doc_tokens = list(document)
        if not doc_tokens:
            continue
        if bos_token_id is not None and doc_tokens[0] != bos_token_id:
            doc_tokens = [bos_token_id] + doc_tokens
        chunks.extend(chunk_document(doc_tokens, sequence_length))
    return chunks


def pack_chunks_best_fit(chunks: Iterable[Sequence[int]], sequence_length: int) -> list[PackedBlock]:
    bins: list[list[int]] = []
    lengths: list[list[int]] = []

    sorted_chunks = sorted((list(chunk) for chunk in chunks), key=len, reverse=True)
    for chunk in sorted_chunks:
        chunk_len = len(chunk)
        best_idx: int | None = None
        best_remaining: int | None = None
        for index, existing in enumerate(bins):
            remaining = sequence_length - len(existing)
            if chunk_len <= remaining:
                leftover = remaining - chunk_len
                if best_remaining is None or leftover < best_remaining:
                    best_idx = index
                    best_remaining = leftover
        if best_idx is None:
            bins.append(chunk.copy())
            lengths.append([chunk_len])
        else:
            bins[best_idx].extend(chunk)
            lengths[best_idx].append(chunk_len)

    packed: list[PackedBlock] = []
    for bin_tokens, chunk_lengths in zip(bins, lengths):
        padding = sequence_length - len(bin_tokens)
        if padding < 0:
            raise AssertionError("overfilled bin")
        packed.append(
            PackedBlock(
                tokens=bin_tokens + ([0] * padding),
                padding_tokens=padding,
                chunk_lengths=chunk_lengths,
            )
        )
    return packed
