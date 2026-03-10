from __future__ import annotations

import unittest

from lab.scoring import assess_experiment_trust


def _experiment(
    *,
    status: str = "completed",
    run_purpose: str = "search",
    validation_state: str = "not_required",
    disposition: str | None = None,
    metric: float | None = 0.97,
) -> dict[str, object]:
    return {
        "status": status,
        "run_purpose": run_purpose,
        "validation_state": validation_state,
        "disposition": disposition,
        "primary_metric_value": metric,
    }


class TrustLabelTests(unittest.TestCase):
    def test_invalid_when_run_missing_metric(self) -> None:
        assessment = assess_experiment_trust(experiment=_experiment(metric=None))
        self.assertEqual(assessment.label, "invalid")

    def test_confirmed_when_validation_passed(self) -> None:
        assessment = assess_experiment_trust(experiment=_experiment(validation_state="passed", disposition="promoted"))
        self.assertEqual(assessment.label, "confirmed")

    def test_audited_when_run_purpose_is_audit(self) -> None:
        assessment = assess_experiment_trust(experiment=_experiment(run_purpose="audit"))
        self.assertEqual(assessment.label, "audited")

    def test_regressed_when_validation_failed(self) -> None:
        assessment = assess_experiment_trust(experiment=_experiment(validation_state="failed", disposition="discarded"))
        self.assertEqual(assessment.label, "regressed")

    def test_provisional_when_pending_validation(self) -> None:
        assessment = assess_experiment_trust(experiment=_experiment(validation_state="pending", disposition="pending_validation"))
        self.assertEqual(assessment.label, "provisional")


if __name__ == "__main__":
    unittest.main()
