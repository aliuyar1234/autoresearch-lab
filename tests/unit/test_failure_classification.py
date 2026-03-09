from __future__ import annotations

import unittest

from lab.runner.failures import classify_failure


class FailureClassificationTests(unittest.TestCase):
    def test_import_error_is_classified(self) -> None:
        result = classify_failure(stderr_text="ModuleNotFoundError: No module named 'imaginary_backend'")
        self.assertEqual(result.crash_class, "import_error")

    def test_oom_train_is_classified(self) -> None:
        result = classify_failure(stderr_text="RuntimeError: CUDA out of memory")
        self.assertEqual(result.crash_class, "oom_train")

    def test_timeout_is_classified(self) -> None:
        result = classify_failure(stderr_text="timed out waiting for target to finish")
        self.assertEqual(result.crash_class, "timeout")

    def test_assertion_is_classified(self) -> None:
        result = classify_failure(stderr_text="AssertionError: metric must be finite")
        self.assertEqual(result.crash_class, "assertion_failure")

    def test_unknown_falls_back_cleanly(self) -> None:
        result = classify_failure(stderr_text="totally novel failure mode")
        self.assertEqual(result.crash_class, "unknown")


if __name__ == "__main__":
    unittest.main()
