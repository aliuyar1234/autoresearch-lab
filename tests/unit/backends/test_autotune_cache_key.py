from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from lab.backends import autotune_cache_key, autotune_shape_family, default_runtime_probe_candidate_set, named_device_profile
from research.dense_gpt.search_space import resolve_dense_config


REPO_ROOT = Path(__file__).resolve().parents[3]


class RuntimeAutotuneKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.campaign = json.loads((REPO_ROOT / "campaigns" / "base_2k" / "campaign.json").read_text(encoding="utf-8"))
        self.profile = named_device_profile("rtx_pro_6000_96gb")

    def test_cache_key_ignores_runtime_overlay_knobs(self) -> None:
        resolved = resolve_dense_config(self.campaign, {}, device_profile=self.profile)
        variant = copy.deepcopy(resolved)
        variant["runtime"]["device_batch_size"] = 192
        variant["runtime"]["eval_batch_size"] = 96
        variant["runtime"]["compile_enabled"] = False
        variant["runtime"]["autotune"] = {
            "cache_key": "ignored",
            "winner": {"runtime_overlay": {"device_batch_size": 192}},
        }

        shape_a = autotune_shape_family(resolved)
        shape_b = autotune_shape_family(variant)
        self.assertEqual(shape_a, shape_b)

        key_a = autotune_cache_key(
            device_profile=self.profile.profile_id,
            backend="sdpa",
            campaign_id=str(self.campaign["campaign_id"]),
            lane="scout",
            sequence_length=int(resolved["resolved"]["sequence_length"]),
            shape_family=shape_a,
        )
        key_b = autotune_cache_key(
            device_profile=self.profile.profile_id,
            backend="sdpa",
            campaign_id=str(self.campaign["campaign_id"]),
            lane="scout",
            sequence_length=int(variant["resolved"]["sequence_length"]),
            shape_family=shape_b,
        )
        self.assertEqual(key_a, key_b)

    def test_candidate_set_stays_inside_profile_ceiling(self) -> None:
        resolved = resolve_dense_config(self.campaign, {}, device_profile=self.profile)
        candidates = default_runtime_probe_candidate_set(
            resolved_config=resolved,
            device_profile=self.profile,
            backend="sdpa",
        )

        self.assertTrue(candidates)
        self.assertLessEqual(
            max(candidate.device_batch_size for candidate in candidates),
            self.profile.safe_device_batch_ceiling,
        )
        self.assertEqual({candidate.compile_enabled for candidate in candidates}, {False, True})
        self.assertEqual(
            {candidate.device_batch_size for candidate in candidates},
            {128, 160, 192},
        )


if __name__ == "__main__":
    unittest.main()
