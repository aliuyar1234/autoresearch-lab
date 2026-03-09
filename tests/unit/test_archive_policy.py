from __future__ import annotations

import json
import unittest

from lab.scheduler.archive import build_archive_snapshot


class ArchivePolicyTests(unittest.TestCase):
    def test_archive_keeps_pareto_and_near_miss(self) -> None:
        experiments = [
            {
                "experiment_id": "exp_champion",
                "lane": "confirm",
                "primary_metric_value": 0.95,
                "peak_vram_gb": 20.0,
                "complexity_cost": 2,
                "disposition": "promoted",
                "proposal_json": json.dumps({"config_overrides": {"optimizer_groups": {"matrix_lr_scale": 1.1}}}),
            },
            {
                "experiment_id": "exp_near_miss",
                "lane": "main",
                "primary_metric_value": 0.951,
                "peak_vram_gb": 18.0,
                "complexity_cost": 1,
                "disposition": "archived",
                "proposal_json": json.dumps({"config_overrides": {"optimizer_groups": {"weight_decay": 0.15}}}),
            },
        ]

        snapshot = build_archive_snapshot(experiments)

        self.assertEqual(snapshot["champions"][0]["experiment_id"], "exp_champion")
        self.assertEqual(snapshot["near_misses"][0]["experiment_id"], "exp_near_miss")
        self.assertEqual(
            {item["experiment_id"] for item in snapshot["pareto"]},
            {"exp_champion", "exp_near_miss"},
        )


if __name__ == "__main__":
    unittest.main()
