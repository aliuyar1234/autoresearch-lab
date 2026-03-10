from __future__ import annotations

import unittest

from lab.night import _continuation_hint


class NightContractsTests(unittest.TestCase):
    def test_interrupted_session_returns_resume_hint(self) -> None:
        hint = _continuation_hint(
            campaign_id="base_2k",
            status="interrupted",
            resume_payload={"status": "recovered"},
            run_count=1,
        )
        self.assertIn("python -m lab.cli night --campaign base_2k", hint)
        self.assertIn("auto-resumes", hint)


if __name__ == "__main__":
    unittest.main()
