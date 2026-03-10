from __future__ import annotations

import unittest

from lab.memory.retrieve import retrieve_memory_context


class RetrievalDiversityTests(unittest.TestCase):
    def test_combine_retrieval_keeps_two_distinct_parent_citations(self) -> None:
        memory_records = [
            {
                "memory_id": "mem_parent_a",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "champion_snapshot",
                "source_kind": "champion",
                "source_ref": "exp_parent_a",
                "family": "exploit",
                "lane": "scout",
                "outcome_label": "promoted",
                "tags": ["depth"],
                "payload": {"config_overrides": {"model": {"depth": 10}}},
                "updated_at": "2026-03-09T12:00:00+00:00",
            },
            {
                "memory_id": "mem_parent_b",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "champion_snapshot",
                "source_kind": "champion",
                "source_ref": "exp_parent_b",
                "family": "exploit",
                "lane": "scout",
                "outcome_label": "promoted",
                "tags": ["embed_lr"],
                "payload": {"config_overrides": {"optimizer_groups": {"embed_lr_scale": 1.1}}},
                "updated_at": "2026-03-08T12:00:00+00:00",
            },
            {
                "memory_id": "mem_warning",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "failure_autopsy",
                "source_kind": "experiment",
                "source_ref": "exp_warning",
                "family": "combine",
                "lane": "scout",
                "outcome_label": "failed",
                "tags": ["combine"],
                "payload": {"config_overrides": {"model": {"n_kv_head": 2}}},
                "updated_at": "2026-03-07T12:00:00+00:00",
            },
            {
                "memory_id": "mem_duplicate_source",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "experiment_result",
                "source_kind": "experiment",
                "source_ref": "exp_warning",
                "family": "combine",
                "lane": "scout",
                "outcome_label": "archived",
                "tags": ["combine"],
                "payload": {"config_overrides": {"optimizer_groups": {"weight_decay": 0.18}}},
                "updated_at": "2026-03-06T12:00:00+00:00",
            },
        ]

        payload = retrieve_memory_context(
            memory_records=memory_records,
            campaign_id="base_2k",
            comparability_group="dense_2k",
            proposal_id="p_combine",
            family="combine",
            lane="scout",
            tags=["combine", "depth", "embed_lr"],
            query_payload={"family": "combine"},
            query_text="combine strong parents",
        )

        evidence = payload["evidence"]
        self.assertLessEqual(len(evidence), 4)
        parent_roles = [item for item in evidence if item["role"] == "combination_parent"]
        self.assertEqual(len(parent_roles), 2)
        self.assertEqual(len({item["source_ref"] for item in evidence}), len(evidence))


if __name__ == "__main__":
    unittest.main()
