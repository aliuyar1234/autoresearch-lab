from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lab.backends import available_backend_candidates, backend_blacklist_path, backend_cache_path, detect_device_profile, select_backend, shape_family_for_run
from lab.campaigns import build_campaign
from lab.campaigns.load import load_campaign
from lab.paths import build_paths, ensure_managed_roots
from lab.settings import load_settings
from research.dense_gpt.search_space import resolve_dense_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def _has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


@unittest.skipUnless(_has_cuda(), "CUDA is required for GPU smoke tests")
class TinyGpuRunTests(unittest.TestCase):
    def _paths_and_campaign(self, temp_root: Path):
        settings = load_settings(
            repo_root=REPO_ROOT,
            artifacts_root=temp_root / "artifacts",
            db_path=temp_root / "lab.sqlite3",
            worktrees_root=temp_root / ".worktrees",
            env={},
        )
        paths = build_paths(settings)
        ensure_managed_roots(paths)
        source_root = temp_root / "raw"
        self._write_base_source_docs(source_root)
        build_campaign(paths, "base_2k", source_dir=source_root)
        return paths, load_campaign(paths, "base_2k")

    def _write_base_source_docs(self, source_root: Path) -> None:
        source_root.mkdir(parents=True, exist_ok=True)
        docs = {
            "shard_00001.parquet": "train example one",
            "shard_00002.parquet": "train example two",
            "shard_06540.parquet": "locked validation",
            "shard_06541.parquet": "audit validation",
            "shard_06542.parquet": "search validation",
        }
        for name, text in docs.items():
            (source_root / name).write_text(text, encoding="utf-8")

    def _run_tiny_train(self, temp_root: Path) -> dict[str, object]:
        paths, campaign = self._paths_and_campaign(temp_root)
        config = resolve_dense_config(campaign, {})
        config_path = temp_root / "tiny_config.json"
        summary_path = temp_root / "tiny_summary.json"
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        profile = detect_device_profile()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "research.dense_gpt.train",
                "--summary-out",
                str(summary_path),
                "--config-path",
                str(config_path),
                "--experiment-id",
                "gpu_smoke_exp",
                "--proposal-id",
                "gpu_smoke_prop",
                "--campaign-id",
                campaign["campaign_id"],
                "--lane",
                "scout",
                "--backend",
                "sdpa",
                "--device-profile",
                profile.profile_id,
                "--repo-root",
                str(paths.repo_root),
                "--artifacts-root",
                str(paths.artifacts_root),
                "--cache-root",
                str(paths.cache_root),
                "--time-budget-seconds",
                "8",
                "--max-steps",
                "3",
                "--eval-batches",
                "1",
                "--tiny",
                "--require-cuda",
            ],
            cwd=paths.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(summary_path.read_text(encoding="utf-8"))

    def test_tiny_gpu_run_emits_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = self._run_tiny_train(Path(tmpdir))
            self.assertEqual(summary["status"], "completed")
            self.assertGreater(summary["tokens_processed"], 0)

    def test_backend_selector_runs_microbench(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            paths, campaign = self._paths_and_campaign(temp_root)
            profile = detect_device_profile()
            candidates = available_backend_candidates(profile)
            self.assertTrue(candidates)
            selection = select_backend(
                cache_path=backend_cache_path(paths),
                blacklist_path=backend_blacklist_path(paths),
                candidates=candidates,
                shape=shape_family_for_run(campaign, resolve_dense_config(campaign, {}), profile, purpose="train"),
                device_profile=profile,
                cuda_version=None,
                torch_version="gpu-test",
                compile_enabled=True,
                force_rebenchmark=True,
            )
            self.assertIn(selection.backend, [candidate.name for candidate in candidates])
            self.assertFalse(selection.from_cache)
            self.assertTrue(selection.benchmark_results)

    def test_config_summary_has_backend_and_device_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = self._run_tiny_train(Path(tmpdir))
            self.assertEqual(summary["backend"], "sdpa")
            self.assertTrue(summary["device_profile"])
            self.assertTrue(summary["config_fingerprint"])
            self.assertGreater(summary["compile_seconds"], 0.0)
            self.assertEqual(summary["warnings"], [])


if __name__ == "__main__":
    unittest.main()
