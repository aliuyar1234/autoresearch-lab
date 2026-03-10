from __future__ import annotations

import unittest
from pathlib import Path

from lab.campaigns.load import load_campaign
from lab.paths import build_paths
from lab.settings import load_settings
from lab.validation.review import _decide_review


REPO_ROOT = Path(__file__).resolve().parents[3]


class ReviewDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = load_settings(repo_root=REPO_ROOT, env={})
        cls.paths = build_paths(settings)
        cls.campaign = load_campaign(cls.paths, "base_2k")

    def test_confirm_review_passes_above_threshold(self) -> None:
        decision, reason, disposition, validation_state = _decide_review(
            campaign=self.campaign,
            source={"complexity_cost": 1},
            comparator={"complexity_cost": 2},
            delta_median=float(self.campaign["promotion"]["champion_min_delta"]) + 0.001,
            mode="confirm",
        )
        self.assertEqual(decision, "passed")
        self.assertEqual(disposition, "promoted")
        self.assertEqual(validation_state, "passed")
        self.assertIn(">=", reason)

    def test_confirm_review_can_pass_complexity_tie_break(self) -> None:
        threshold = float(self.campaign["promotion"]["champion_min_delta"])
        tie_threshold = float(self.campaign["primary_metric"]["tie_threshold"])
        decision, _, disposition, validation_state = _decide_review(
            campaign=self.campaign,
            source={"complexity_cost": 1},
            comparator={"complexity_cost": 3},
            delta_median=threshold - (tie_threshold / 2.0),
            mode="confirm",
        )
        self.assertEqual(decision, "passed")
        self.assertEqual(disposition, "promoted")
        self.assertEqual(validation_state, "passed")

    def test_confirm_review_fails_when_delta_is_negative(self) -> None:
        decision, _, disposition, validation_state = _decide_review(
            campaign=self.campaign,
            source={"complexity_cost": 2},
            comparator={"complexity_cost": 1},
            delta_median=-0.001,
            mode="confirm",
        )
        self.assertEqual(decision, "failed")
        self.assertEqual(disposition, "discarded")
        self.assertEqual(validation_state, "failed")


if __name__ == "__main__":
    unittest.main()
