from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.backends import named_device_profile
from lab.campaigns.load import load_campaign
from lab.paths import build_paths
from lab.settings import load_settings
from research.dense_gpt.mutation_rules import apply_path_override, mutation_respects_campaign_constraints
from research.dense_gpt.search_space import resolve_dense_config, search_knobs_for_campaign, validate_dense_config


REPO_ROOT = Path(__file__).resolve().parents[2]


class SearchSpaceTests(unittest.TestCase):
    def _campaign(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            settings = load_settings(
                repo_root=REPO_ROOT,
                artifacts_root=temp_root / "artifacts",
                db_path=temp_root / "lab.sqlite3",
                worktrees_root=temp_root / ".worktrees",
                env={},
            )
            paths = build_paths(settings)
            return load_campaign(paths, "base_2k")

    def test_search_space_legality(self) -> None:
        campaign = self._campaign()
        resolved = resolve_dense_config(campaign, {})
        self.assertEqual(validate_dense_config(campaign, resolved), [])

        invalid = resolve_dense_config(
            campaign,
            {
                "model": {
                    "n_kv_head": 3,
                    "window_pattern": "SSSS",
                }
            },
        )
        issues = validate_dense_config(campaign, invalid)
        self.assertTrue(any("n_kv_head" in issue for issue in issues))
        self.assertTrue(any("window_pattern" in issue for issue in issues))

    def test_mutation_rules_respect_campaign_constraints(self) -> None:
        campaign = self._campaign()
        device_profile = named_device_profile("generic_single_gpu_nvidia")

        legal = apply_path_override({}, "optimizer_groups.embed_lr_scale", 1.25)
        ok, issues = mutation_respects_campaign_constraints(campaign, legal, device_profile=device_profile)
        self.assertTrue(ok)
        self.assertEqual(issues, [])

        illegal = {
            "runtime": {"device_batch_size": 9999},
            "curriculum": {"progressive_depth": {"enabled": True, "warmup_fraction": 0.3, "min_depth": 99}},
        }
        ok, issues = mutation_respects_campaign_constraints(campaign, illegal, device_profile=device_profile)
        self.assertFalse(ok)
        self.assertTrue(any("safe ceiling" in issue or "min_depth" in issue for issue in issues))

        knob_paths = {knob.path for knob in search_knobs_for_campaign(campaign, "scout")}
        for required in (
            "model.depth",
            "model.aspect_ratio",
            "model.head_dim",
            "model.n_kv_head",
            "model.window_pattern",
            "optimizer_groups.embed_lr_scale",
            "optimizer_groups.unembed_lr_scale",
            "optimizer_groups.matrix_lr_scale",
            "optimizer_groups.scalar_lr_scale",
            "optimizer_groups.weight_decay",
            "schedule.warmdown_ratio",
            "model.rope_base",
            "model.ema_at_eval",
            "curriculum.sequence_curriculum.enabled",
            "curriculum.progressive_depth.enabled",
        ):
            self.assertIn(required, knob_paths)


if __name__ == "__main__":
    unittest.main()
