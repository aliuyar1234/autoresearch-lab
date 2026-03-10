from __future__ import annotations

import unittest

from lab.scheduler.exhaustion import compute_idea_signature, scientific_mutation_paths


class IdeaSignatureTests(unittest.TestCase):
    def test_runtime_only_overrides_do_not_change_scientific_signature(self) -> None:
        left = {
            "model": {"depth": 10},
            "runtime": {"device_batch_size": 8, "autotune": {"winner": "candidate_a"}},
        }
        right = {
            "model": {"depth": 10},
            "runtime": {"device_batch_size": 16, "autotune": {"winner": "candidate_b"}},
        }

        self.assertEqual(compute_idea_signature(left), compute_idea_signature(right))
        self.assertEqual(scientific_mutation_paths(left), ["model.depth"])


if __name__ == "__main__":
    unittest.main()
