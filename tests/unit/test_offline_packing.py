from __future__ import annotations

import unittest

from lab.campaigns.packing import pack_tokenized_documents


class OfflinePackingTests(unittest.TestCase):
    def test_offline_packer_is_deterministic(self) -> None:
        tokenized_documents = [[10, 11, 12], [20, 21], [30, 31, 32, 33]]
        first = pack_tokenized_documents(tokenized_documents, sequence_length=8, bos_token_id=1)
        second = pack_tokenized_documents(tokenized_documents, sequence_length=8, bos_token_id=1)
        self.assertEqual(first, second)

    def test_offline_packer_preserves_bos_alignment(self) -> None:
        tokenized_documents = [[10, 11], [20, 21, 22], [30]]
        blocks = pack_tokenized_documents(tokenized_documents, sequence_length=6, bos_token_id=1)
        for block in blocks:
            offset = 0
            for chunk_length in block.chunk_lengths:
                self.assertEqual(block.tokens[offset], 1)
                offset += chunk_length


if __name__ == "__main__":
    unittest.main()
