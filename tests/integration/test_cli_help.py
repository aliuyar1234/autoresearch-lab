from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_repo_skeleton(repo_root: Path) -> None:
    (repo_root / "docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "schemas").mkdir(parents=True, exist_ok=True)
    (repo_root / "sql").mkdir(parents=True, exist_ok=True)
    (repo_root / "campaigns" / "base_2k").mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='tmp'\n", encoding="utf-8")
    (repo_root / "README.md").write_text("# tmp\n", encoding="utf-8")
    (repo_root / "docs" / "runbook.md").write_text("# runbook\n", encoding="utf-8")
    (repo_root / "schemas" / "campaign.schema.json").write_text("{}\n", encoding="utf-8")
    (repo_root / "sql" / "001_ledger.sql").write_text("CREATE TABLE IF NOT EXISTS t(id INTEGER);\n", encoding="utf-8")
    (repo_root / "campaigns" / "base_2k" / "campaign.json").write_text(
        json.dumps(
            {
                "campaign_id": "base_2k",
                "assets": {
                    "root": "artifacts/cache/campaigns/base_2k",
                    "tokenizer_manifest": "tokenizer.manifest.json",
                    "pretok_manifest": "pretok.manifest.json",
                    "packed_manifest": "packed.manifest.json",
                },
                "tokenizer": {"artifact_files": ["tokenizer.json"]},
            }
        ),
        encoding="utf-8",
    )


class CliHelpTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "lab.cli", *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_arlab(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["uv", "run", "arlab", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_help_commands_work(self) -> None:
        result = self._run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Autoresearch Lab: a local, single-GPU, CUDA-first, dense-model research lab.", result.stdout)
        self.assertIn("Common path: bootstrap -> preflight -> campaign build -> run -> night -> report -> doctor -> cleanup", result.stdout)
        self.assertLess(result.stdout.index("bootstrap"), result.stdout.index("preflight"))
        self.assertLess(result.stdout.index("preflight"), result.stdout.index("campaign"))
        self.assertLess(result.stdout.index("campaign"), result.stdout.index("run"))
        self.assertLess(result.stdout.index("run"), result.stdout.index("night"))
        self.assertLess(result.stdout.index("night"), result.stdout.index("report"))
        self.assertLess(result.stdout.index("report"), result.stdout.index("doctor"))
        self.assertLess(result.stdout.index("doctor"), result.stdout.index("cleanup"))
        self.assertIn("[optional code lane] export a code-lane task pack", result.stdout)
        self.assertIn("[maintenance] diagnose ledger and artifact health", result.stdout)

        subcommand = self._run_cli("bootstrap", "--help")
        self.assertEqual(subcommand.returncode, 0, subcommand.stderr)
        self.assertIn("--repo-root", subcommand.stdout)

    def test_arlab_entrypoint_help_works(self) -> None:
        result = self._run_arlab("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: arlab", result.stdout)
        self.assertIn("Autoresearch Lab: a local, single-GPU, CUDA-first, dense-model research lab.", result.stdout)

    def test_parse_time_validation_handles_required_flags_and_mutex(self) -> None:
        campaign_show = self._run_cli("campaign", "show")
        self.assertEqual(campaign_show.returncode, 2)
        self.assertIn("--campaign", campaign_show.stderr)

        report = self._run_cli("report")
        self.assertEqual(report.returncode, 2)
        self.assertIn("--campaign", report.stderr)

        autotune = self._run_cli("autotune", "--campaign", "base_2k")
        self.assertEqual(autotune.returncode, 2)
        self.assertIn("--lane", autotune.stderr)
        self.assertIn("--all-lanes", autotune.stderr)

        cleanup = self._run_cli("cleanup", "--apply", "--dry-run")
        self.assertEqual(cleanup.returncode, 2)
        self.assertIn("--dry-run", cleanup.stderr)

    def test_preflight_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_repo = Path(tmpdir)
            _write_repo_skeleton(target_repo)

            bootstrap = self._run_cli("bootstrap", "--repo-root", str(target_repo), "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            preflight = self._run_cli("preflight", "--repo-root", str(target_repo), "--campaign", "base_2k", "--json")
            self.assertEqual(preflight.returncode, 3, preflight.stderr)
            payload = json.loads(preflight.stdout)
            self.assertIn("ok", payload)
            self.assertEqual(payload["command"], "preflight")
            self.assertIn("status", payload)
            self.assertIn("message", payload)
            self.assertIn("warnings", payload)


if __name__ == "__main__":
    unittest.main()
