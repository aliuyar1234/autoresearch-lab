from __future__ import annotations

import unittest

from lab.reports.recommendations import build_recommendations


class ReportRecommendationTests(unittest.TestCase):
    def test_recommendations_surface_repeated_crashes_and_helpful_regions(self) -> None:
        notes = build_recommendations(
            recent_crash_classes=["oom_train", "oom_train", "oom_train"],
            repeated_helpful_tags=["optimizer.embed_lr_scale", "optimizer.embed_lr_scale", "model.depth"],
            repeated_harmful_tags=[],
            near_miss_count=0,
            confirm_promotions=1,
        )
        self.assertTrue(any("Reliability first" in note for note in notes))
        self.assertTrue(any("Exploit region" in note for note in notes))

    def test_recommendations_fall_back_to_default_guidance(self) -> None:
        notes = build_recommendations(
            recent_crash_classes=[],
            repeated_helpful_tags=[],
            repeated_harmful_tags=[],
            near_miss_count=0,
            confirm_promotions=1,
        )
        self.assertEqual(notes, ["Continue structured exploit around the current champion and strongest near-miss."])


if __name__ == "__main__":
    unittest.main()
