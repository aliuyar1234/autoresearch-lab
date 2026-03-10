from __future__ import annotations

import unittest

from lab.memory.retrieve import retrieve_memory_context


class RetrievalScoringTests(unittest.TestCase):
    def test_retrieval_prefers_same_campaign_and_keeps_warning(self) -> None:
        memory_records = [
            {
                "memory_id": "mem_local_win",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "champion_snapshot",
                "source_kind": "champion",
                "source_ref": "exp_local_win",
                "family": "exploit",
                "lane": "scout",
                "outcome_label": "promoted",
                "tags": ["embed_lr", "optimizer_groups.embed_lr_scale"],
                "updated_at": "2026-03-09T12:00:00+00:00",
            },
            {
                "memory_id": "mem_warning",
                "campaign_id": "base_2k",
                "comparability_group": "dense_2k",
                "record_type": "failure_autopsy",
                "source_kind": "experiment",
                "source_ref": "exp_warning",
                "family": "exploit",
                "lane": "scout",
                "outcome_label": "failed",
                "tags": ["embed_lr", "oom_train"],
                "updated_at": "2026-03-08T12:00:00+00:00",
            },
            {
                "memory_id": "mem_other_campaign",
                "campaign_id": "stories_2k",
                "comparability_group": "dense_2k",
                "record_type": "experiment_result",
                "source_kind": "experiment",
                "source_ref": "exp_other_campaign",
                "family": "exploit",
                "lane": "scout",
                "outcome_label": "archived",
                "tags": ["embed_lr"],
                "updated_at": "2026-03-07T12:00:00+00:00",
            },
        ]

        payload = retrieve_memory_context(
            memory_records=memory_records,
            campaign_id="base_2k",
            comparability_group="dense_2k",
            proposal_id="p_test",
            family="exploit",
            lane="scout",
            tags=["embed_lr", "optimizer_groups.embed_lr_scale"],
            query_payload={"family": "exploit"},
            query_text="exploit embed lr",
        )

        self.assertTrue(str(payload["retrieval_event_id"]).startswith("ret_"))
        self.assertEqual(payload["items"][0]["memory_id"], "mem_local_win")
        evidence_roles = {item["role"] for item in payload["evidence"]}
        self.assertIn("warning", evidence_roles)
        self.assertIn("supporting_precedent", evidence_roles)


if __name__ == "__main__":
    unittest.main()
