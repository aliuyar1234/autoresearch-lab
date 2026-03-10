from __future__ import annotations

import unittest

from lab.scheduler.exhaustion import exhaustion_summary, is_exhausted_signature


class ExhaustionPolicyTests(unittest.TestCase):
    def test_failed_signature_becomes_exhausted(self) -> None:
        experiments = [
            {
                "experiment_id": "exp_failed_1",
                "campaign_id": "base_2k",
                "idea_signature": "sig_dead",
                "status": "failed",
                "disposition": "discarded",
                "validation_state": "not_required",
            },
            {
                "experiment_id": "exp_failed_2",
                "campaign_id": "base_2k",
                "idea_signature": "sig_dead",
                "status": "failed",
                "disposition": "discarded",
                "validation_state": "failed",
            },
            {
                "experiment_id": "exp_alive",
                "campaign_id": "base_2k",
                "idea_signature": "sig_alive",
                "status": "completed",
                "disposition": "pending_validation",
                "validation_state": "pending",
            },
        ]

        summary = exhaustion_summary(experiments, campaign_id="base_2k")
        self.assertTrue(summary["sig_dead"]["exhausted"])
        self.assertFalse(summary["sig_alive"]["exhausted"])
        self.assertTrue(is_exhausted_signature("sig_dead", experiments=experiments, campaign_id="base_2k"))
        self.assertFalse(is_exhausted_signature("sig_alive", experiments=experiments, campaign_id="base_2k"))


if __name__ == "__main__":
    unittest.main()
