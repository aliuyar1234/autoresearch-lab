from __future__ import annotations

import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.paths import build_paths
from lab.scoring import BaselineRecord, explain_experiment_score
from lab.settings import load_settings


REPO_ROOT = Path(__file__).resolve().parents[2]


def _experiment(*, experiment_id: str, lane: str, metric: float, complexity_cost: int, status: str = "completed") -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "campaign_id": "base_2k",
        "lane": lane,
        "status": status,
        "primary_metric_value": metric,
        "complexity_cost": complexity_cost,
    }


class PromotionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = load_settings(repo_root=REPO_ROOT, env={})
        cls.paths = build_paths(settings)
        cls.campaign = load_campaign(cls.paths, "base_2k")

    def test_promotion_rule_below_threshold(self) -> None:
        baseline = BaselineRecord(experiment_id="exp_base", metric_value=0.98, complexity_cost=1)
        explanation = explain_experiment_score(
            experiment=_experiment(experiment_id="exp_candidate", lane="scout", metric=0.9797, complexity_cost=1),
            campaign=self.campaign,
            baseline=baseline,
        )
        self.assertEqual(explanation.final_disposition, "discarded")
        self.assertAlmostEqual(explanation.metric_delta or 0.0, 0.0003, places=6)

    def test_promotion_rule_simple_win(self) -> None:
        baseline = BaselineRecord(experiment_id="exp_base", metric_value=0.98, complexity_cost=2)
        explanation = explain_experiment_score(
            experiment=_experiment(experiment_id="exp_candidate", lane="main", metric=0.979, complexity_cost=2),
            campaign=self.campaign,
            baseline=baseline,
        )
        self.assertEqual(explanation.final_disposition, "promoted")
        self.assertEqual(explanation.archive_effect, "advance_to_confirm")

    def test_promotion_rule_tie_prefers_lower_complexity(self) -> None:
        baseline = BaselineRecord(experiment_id="exp_base", metric_value=0.98, complexity_cost=3)
        explanation = explain_experiment_score(
            experiment=_experiment(experiment_id="exp_candidate", lane="main", metric=0.9801, complexity_cost=1),
            campaign=self.campaign,
            baseline=baseline,
        )
        self.assertEqual(explanation.final_disposition, "archived")
        self.assertTrue(explanation.complexity_tie_break_applied)


if __name__ == "__main__":
    unittest.main()
