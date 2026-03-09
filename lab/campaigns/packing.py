from __future__ import annotations

from typing import Iterable, Sequence

from reference_impl.offline_packing import PackedBlock, pack_chunks_best_fit, prepare_chunks


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
