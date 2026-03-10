from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.integration._cli_helpers import missing_preflight_imports, run_cli


def _has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


@unittest.skipUnless(_has_cuda() and not missing_preflight_imports(), "CUDA plus preflight dependencies are required for GPU smoke tests")
class SmokeCliGpuTests(unittest.TestCase):
    def test_smoke_cli_gpu(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            smoke = run_cli("smoke", temp_root, "--gpu", "--json")
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            payload = json.loads(smoke.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["warnings"], [])
            self.assertTrue(payload["tiny_gpu_run"]["ok"])
            summary = payload["tiny_gpu_run"]["summary"]
            self.assertGreater(float(summary["compile_seconds"]), 0.0)
            self.assertEqual(summary["warnings"], [])


if __name__ == "__main__":
    unittest.main()
