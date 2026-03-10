from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


def improvement(direction: str, baseline: float, candidate: float) -> float:
    if direction == "min":
        return baseline - candidate
    if direction == "max":
        return candidate - baseline
    raise ValueError(f"unsupported metric direction: {direction}")


@dataclass(frozen=True)
class BaselineRecord:
    experiment_id: str
    metric_value: float
    complexity_cost: int | None


@dataclass(frozen=True)
class Thresholds:
    scout_to_main_min_delta: float
    main_to_confirm_min_delta: float
    champion_min_delta: float
    tie_threshold: float
    allow_complexity_tie_break: bool = True


@dataclass(frozen=True)
class Candidate:
    metric_value: float
    complexity_cost: int
    audit_ok: bool = True
    confirm_ok: bool = True
    review_required: bool = False
    comparable: bool = True
    valid: bool = True


@dataclass(frozen=True)
class PromotionDecision:
    disposition: str
    reason: str


@dataclass(frozen=True)
class ScoreExplanation:
    experiment_id: str
    campaign_id: str
    lane: str
    run_purpose: str
    eval_split: str
    baseline_experiment_id: str | None
    baseline_metric_value: float | None
    candidate_metric_value: float
    metric_direction: str
    metric_delta: float | None
    promotion_threshold: float | None
    tie_threshold: float
    complexity_cost: int | None
    complexity_tie_break_applied: bool
    final_disposition: str
    validation_state: str
    archive_effect: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrustAssessment:
    label: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def best_baseline(experiments: Iterable[dict[str, Any]], *, direction: str) -> BaselineRecord | None:
    best_row: dict[str, Any] | None = None
    best_metric: float | None = None
    for row in experiments:
        metric_value = row.get("primary_metric_value")
        if metric_value is None:
            continue
        metric = float(metric_value)
        if best_row is None:
            best_row = row
            best_metric = metric
            continue
        assert best_metric is not None
        if direction == "min" and metric < best_metric:
            best_row = row
            best_metric = metric
        elif direction == "max" and metric > best_metric:
            best_row = row
            best_metric = metric
    if best_row is None or best_metric is None:
        return None
    return BaselineRecord(
        experiment_id=str(best_row["experiment_id"]),
        metric_value=best_metric,
        complexity_cost=int(best_row["complexity_cost"]) if best_row.get("complexity_cost") is not None else None,
    )


def explain_experiment_score(
    *,
    experiment: dict[str, Any],
    campaign: dict[str, Any],
    baseline: BaselineRecord | None,
) -> ScoreExplanation:
    direction = str(campaign["primary_metric"]["direction"])
    threshold = _threshold_for_lane(campaign, str(experiment["lane"]))
    tie_threshold = float(campaign["primary_metric"]["tie_threshold"])
    candidate_metric = float(experiment["primary_metric_value"])
    complexity_cost = int(experiment["complexity_cost"]) if experiment.get("complexity_cost") is not None else 0
    run_purpose = str(experiment.get("run_purpose") or "search")
    eval_split = str(experiment.get("eval_split") or "search_val")
    validation_state = str(experiment.get("validation_state") or "not_required")
    review_required = _requires_validation(experiment)

    if str(experiment["status"]) != "completed":
        return ScoreExplanation(
            experiment_id=str(experiment["experiment_id"]),
            campaign_id=str(experiment["campaign_id"]),
            lane=str(experiment["lane"]),
            run_purpose=run_purpose,
            eval_split=eval_split,
            baseline_experiment_id=baseline.experiment_id if baseline else None,
            baseline_metric_value=baseline.metric_value if baseline else None,
            candidate_metric_value=candidate_metric,
            metric_direction=direction,
            metric_delta=improvement(direction, baseline.metric_value, candidate_metric) if baseline else None,
            promotion_threshold=threshold,
            tie_threshold=tie_threshold,
            complexity_cost=complexity_cost,
            complexity_tie_break_applied=False,
            final_disposition="failed",
            validation_state=validation_state,
            archive_effect="crash_exemplar",
            reason="invalid terminal run",
        )

    if baseline is None:
        if review_required:
            return ScoreExplanation(
                experiment_id=str(experiment["experiment_id"]),
                campaign_id=str(experiment["campaign_id"]),
                lane=str(experiment["lane"]),
                run_purpose=run_purpose,
                eval_split=eval_split,
                baseline_experiment_id=None,
                baseline_metric_value=None,
                candidate_metric_value=candidate_metric,
                metric_direction=direction,
                metric_delta=None,
                promotion_threshold=threshold,
                tie_threshold=tie_threshold,
                complexity_cost=complexity_cost,
                complexity_tie_break_applied=False,
                final_disposition="pending_validation",
                validation_state="pending",
                archive_effect="await_validation",
                reason="confirm candidate has no prior comparable champion; pending validation review",
            )
        return ScoreExplanation(
            experiment_id=str(experiment["experiment_id"]),
            campaign_id=str(experiment["campaign_id"]),
            lane=str(experiment["lane"]),
            run_purpose=run_purpose,
            eval_split=eval_split,
            baseline_experiment_id=None,
            baseline_metric_value=None,
            candidate_metric_value=candidate_metric,
            metric_direction=direction,
            metric_delta=None,
            promotion_threshold=threshold,
            tie_threshold=tie_threshold,
            complexity_cost=complexity_cost,
            complexity_tie_break_applied=False,
            final_disposition="promoted",
            validation_state=validation_state,
            archive_effect=_archive_effect_for_disposition(str(experiment["lane"]), "promoted"),
            reason="no prior comparable baseline; established lane baseline",
        )

    decision = decide_lane_promotion(
        lane=str(experiment["lane"]),
        direction=direction,
        baseline_metric=baseline.metric_value,
        candidate=Candidate(
            metric_value=candidate_metric,
            complexity_cost=complexity_cost,
            audit_ok=True,
            confirm_ok=True,
            review_required=review_required,
            comparable=True,
            valid=True,
        ),
        thresholds=Thresholds(
            scout_to_main_min_delta=float(campaign["promotion"]["scout_to_main_min_delta"]),
            main_to_confirm_min_delta=float(campaign["promotion"]["main_to_confirm_min_delta"]),
            champion_min_delta=float(campaign["promotion"]["champion_min_delta"]),
            tie_threshold=tie_threshold,
            allow_complexity_tie_break=bool(campaign["promotion"].get("allow_complexity_tie_break", True)),
        ),
    )
    delta = improvement(direction, baseline.metric_value, candidate_metric)
    return ScoreExplanation(
        experiment_id=str(experiment["experiment_id"]),
        campaign_id=str(experiment["campaign_id"]),
        lane=str(experiment["lane"]),
        run_purpose=run_purpose,
        eval_split=eval_split,
        baseline_experiment_id=baseline.experiment_id,
        baseline_metric_value=baseline.metric_value,
        candidate_metric_value=candidate_metric,
        metric_direction=direction,
        metric_delta=delta,
        promotion_threshold=threshold,
        tie_threshold=tie_threshold,
        complexity_cost=complexity_cost,
        complexity_tie_break_applied="nearly tied but simpler" in decision.reason,
        final_disposition=decision.disposition,
        validation_state=_validation_state_for_disposition(decision.disposition, existing=validation_state),
        archive_effect=_archive_effect_for_disposition(str(experiment["lane"]), decision.disposition),
        reason=decision.reason,
    )


def assess_experiment_trust(
    *,
    experiment: dict[str, Any],
    direction: str | None = None,
    baseline_metric: float | None = None,
) -> TrustAssessment:
    status = str(experiment.get("status") or "unknown")
    run_purpose = str(experiment.get("run_purpose") or "search")
    validation_state = str(experiment.get("validation_state") or "not_required")
    disposition = str(experiment.get("disposition") or "")
    metric_value = experiment.get("primary_metric_value")

    if status != "completed" or metric_value is None:
        return TrustAssessment("invalid", "run did not finish with a usable metric")

    if run_purpose == "audit":
        return TrustAssessment("audited", "measured on the audit split for robustness, not as a headline search win")

    if validation_state == "passed":
        return TrustAssessment("confirmed", "survived confirm review against a comparable baseline")

    if validation_state == "failed":
        return TrustAssessment("regressed", "failed confirm or audit review against the comparator")

    if disposition in {"archived", "discarded"}:
        delta_text = _regression_delta_text(direction=direction, baseline_metric=baseline_metric, metric_value=metric_value)
        if delta_text:
            return TrustAssessment("regressed", f"completed, but regressed versus the comparator {delta_text}")
        return TrustAssessment("regressed", "completed, but did not hold up as a keep-worthy result")

    if disposition == "pending_validation":
        return TrustAssessment("provisional", "cleared the confirm bar, but still needs a completed validation review")

    if run_purpose == "replay":
        return TrustAssessment("provisional", "replay result outside the promotion path; useful for inspection, not the main leaderboard")

    return TrustAssessment("provisional", "search result has not yet survived confirm or audit review")


def _threshold_for_lane(campaign: dict[str, Any], lane: str) -> float:
    promotion = campaign["promotion"]
    if lane == "scout":
        return float(promotion["scout_to_main_min_delta"])
    if lane == "main":
        return float(promotion["main_to_confirm_min_delta"])
    if lane == "confirm":
        return float(promotion["champion_min_delta"])
    raise ValueError(f"unsupported lane: {lane}")


def _archive_effect_for_disposition(lane: str, disposition: str) -> str:
    if disposition == "failed":
        return "crash_exemplar"
    if disposition == "discarded":
        return "discard"
    if disposition == "archived":
        return "near_miss_archive"
    if disposition == "pending_validation":
        return "await_validation"
    if disposition != "promoted":
        return "unknown"
    if lane == "scout":
        return "advance_to_main"
    if lane == "main":
        return "advance_to_confirm"
    if lane == "confirm":
        return "champion"
    return "unknown"


def _requires_validation(experiment: dict[str, Any]) -> bool:
    return (
        str(experiment.get("lane")) == "confirm"
        and str(experiment.get("run_purpose") or "search") in {"search", "baseline"}
        and str(experiment.get("validation_state") or "not_required") != "passed"
    )


def _validation_state_for_disposition(disposition: str, *, existing: str) -> str:
    if disposition == "pending_validation":
        return "pending"
    if disposition == "promoted":
        return "passed" if existing == "passed" else existing
    if disposition in {"archived", "discarded"} and existing == "pending":
        return "failed"
    return existing


def _regression_delta_text(*, direction: str | None, baseline_metric: float | None, metric_value: Any) -> str | None:
    if direction not in {"min", "max"} or baseline_metric is None or metric_value is None:
        return None
    try:
        delta = improvement(str(direction), float(baseline_metric), float(metric_value))
    except (TypeError, ValueError):
        return None
    return f"(delta={delta:.6f})"


def decide_lane_promotion(
    *,
    lane: str,
    direction: str,
    baseline_metric: float,
    candidate: Candidate,
    thresholds: Thresholds,
) -> PromotionDecision:
    if not candidate.valid:
        return PromotionDecision("failed", "invalid terminal run")
    if not candidate.comparable:
        return PromotionDecision("discarded", "not comparable")

    delta = improvement(direction, baseline_metric, candidate.metric_value)

    if lane == "scout":
        needed = thresholds.scout_to_main_min_delta
        if delta >= needed:
            return PromotionDecision("promoted", f"scout improvement {delta:.6f} >= {needed:.6f}")
        return PromotionDecision("discarded", f"scout improvement {delta:.6f} < {needed:.6f}")

    if lane == "main":
        needed = thresholds.main_to_confirm_min_delta
        if delta >= needed:
            return PromotionDecision("promoted", f"main improvement {delta:.6f} >= {needed:.6f}")
        if thresholds.allow_complexity_tie_break and abs(delta) <= thresholds.tie_threshold and candidate.complexity_cost <= 1:
            return PromotionDecision("archived", "main nearly tied but simpler")
        return PromotionDecision("discarded", f"main improvement {delta:.6f} < {needed:.6f}")

    if lane == "confirm":
        needed = thresholds.champion_min_delta
        if not candidate.audit_ok or not candidate.confirm_ok:
            return PromotionDecision("discarded", "confirm candidate failed audit or confirm checks")
        if delta >= needed:
            if candidate.review_required:
                return PromotionDecision(
                    "pending_validation",
                    f"champion improvement {delta:.6f} >= {needed:.6f}; pending validation review",
                )
            return PromotionDecision("promoted", f"champion improvement {delta:.6f} >= {needed:.6f}")
        if thresholds.allow_complexity_tie_break and abs(delta) <= thresholds.tie_threshold and candidate.complexity_cost <= 1:
            return PromotionDecision("archived", "confirm nearly tied but simpler")
        return PromotionDecision("archived", f"confirm improvement {delta:.6f} < {needed:.6f}")

    raise ValueError(f"unsupported lane: {lane}")
