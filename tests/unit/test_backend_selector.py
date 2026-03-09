from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lab.backends import BackendCandidate, ShapeFamily, named_device_profile, select_backend
from lab.backends.cache import append_blacklist_entry


class BackendSelectorTests(unittest.TestCase):
    def test_backend_selector_cache_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            profile = named_device_profile("generic_single_gpu_nvidia")
            candidates = [
                BackendCandidate("sdpa", "2.7.0"),
                BackendCandidate("kernels", "1.0.0"),
            ]
            shape = ShapeFamily(
                family_id="base_2k_train",
                sequence_length=2048,
                batch_size=8,
                head_count=4,
                kv_head_count=4,
                head_dim=128,
                dtype="bfloat16",
            )
            calls: list[str] = []

            def fake_bench(candidate: BackendCandidate, _shape: ShapeFamily):
                calls.append(candidate.name)
                if candidate.name == "sdpa":
                    from lab.backends import BenchmarkOutcome

                    return BenchmarkOutcome(candidate, True, 1.5, "ok")
                from lab.backends import BenchmarkOutcome

                return BenchmarkOutcome(candidate, True, 2.5, "ok")

            first = select_backend(
                cache_path=temp_root / "cache.json",
                blacklist_path=temp_root / "blacklist.json",
                candidates=candidates,
                shape=shape,
                device_profile=profile,
                cuda_version="12.8",
                torch_version="2.7.0",
                compile_enabled=True,
                benchmark_fn=fake_bench,
            )
            self.assertEqual(first.backend, "sdpa")
            self.assertFalse(first.from_cache)
            self.assertEqual(calls, ["sdpa", "kernels"])

            calls.clear()
            second = select_backend(
                cache_path=temp_root / "cache.json",
                blacklist_path=temp_root / "blacklist.json",
                candidates=candidates,
                shape=shape,
                device_profile=profile,
                cuda_version="12.8",
                torch_version="2.7.0",
                compile_enabled=True,
                benchmark_fn=fake_bench,
            )
            self.assertEqual(second.backend, "sdpa")
            self.assertTrue(second.from_cache)
            self.assertEqual(calls, [])

    def test_backend_selector_blacklist_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            profile = named_device_profile("generic_single_gpu_nvidia")
            candidates = [
                BackendCandidate("sdpa", "2.7.0"),
                BackendCandidate("kernels", "1.0.0"),
            ]
            shape = ShapeFamily(
                family_id="base_2k_train",
                sequence_length=2048,
                batch_size=8,
                head_count=4,
                kv_head_count=4,
                head_dim=128,
                dtype="bfloat16",
            )
            blacklist_path = temp_root / "blacklist.json"
            append_blacklist_entry(blacklist_path, backend="sdpa", shape_family=shape.family_id, reason="backend_unavailable")

            def fake_bench(candidate: BackendCandidate, _shape: ShapeFamily):
                from lab.backends import BenchmarkOutcome

                if candidate.name == "sdpa":
                    return BenchmarkOutcome(candidate, True, 1.0, "fast but blacklisted")
                return BenchmarkOutcome(candidate, True, 2.0, "fallback")

            selected = select_backend(
                cache_path=temp_root / "cache.json",
                blacklist_path=blacklist_path,
                candidates=candidates,
                shape=shape,
                device_profile=profile,
                cuda_version="12.8",
                torch_version="2.7.0",
                compile_enabled=True,
                benchmark_fn=fake_bench,
            )
            self.assertEqual(selected.backend, "kernels")
            self.assertFalse(selected.from_cache)


if __name__ == "__main__":
    unittest.main()
