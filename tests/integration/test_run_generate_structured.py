from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from ._cli_helpers import SUCCESS_TARGET, run_cli, target_json_command


def _generated_target_command() -> str:
    return target_json_command(
        [
            sys.executable,
            str(SUCCESS_TARGET),
            "--summary-out",
            "{summary_out}",
            "--experiment-id",
            "{experiment_id}",
            "--proposal-id",
            "{proposal_id}",
            "--campaign-id",
            "{campaign_id}",
            "--lane",
            "{lane}",
            "--backend",
            "{backend}",
            "--device-profile",
            "{device_profile}",
        ]
    )


class RunGenerateStructuredTests(unittest.TestCase):
    def test_run_generate_structured_baseline_then_exploit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)

            bootstrap = run_cli("bootstrap", temp_root, "--json")
            self.assertEqual(bootstrap.returncode, 0, bootstrap.stderr)

            first = run_cli(
                "run",
                temp_root,
                "--campaign",
                "base_2k",
                "--generate",
                "structured",
                "--lane",
                "scout",
                "--target-command-json",
                _generated_target_command(),
                "--json",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            first_payload = json.loads(first.stdout)
            self.assertEqual(first_payload["proposal_family"], "baseline")
            first_proposal_snapshot = json.loads(
                (temp_root / "artifacts" / "proposals" / f"{first_payload['proposal_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(first_proposal_snapshot["config_overrides"], {})

            second = run_cli(
                "run",
                temp_root,
                "--campaign",
                "base_2k",
                "--generate",
                "structured",
                "--lane",
                "scout",
                "--target-command-json",
                _generated_target_command(),
                "--json",
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            second_payload = json.loads(second.stdout)
            self.assertEqual(second_payload["proposal_family"], "exploit")
            second_proposal_snapshot = json.loads(
                (temp_root / "artifacts" / "proposals" / f"{second_payload['proposal_id']}.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(second_proposal_snapshot["config_overrides"], {})
            self.assertNotEqual(second_proposal_snapshot["config_fingerprint"], first_proposal_snapshot["config_fingerprint"])


if __name__ == "__main__":
    unittest.main()
