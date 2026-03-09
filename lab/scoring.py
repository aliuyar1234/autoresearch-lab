from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from reference_impl.promotion_policy import Candidate, Thresholds, decide_lane_promotion


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
class ScoreExplanation:
    experiment_id: str
    campaign_id: str
    lane: str
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
    archive_effect: str
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

    if str(experiment["status"]) != "completed":
        return ScoreExplanation(
            experiment_id=str(experiment["experiment_id"]),
            campaign_id=str(experiment["campaign_id"]),
            lane=str(experiment["lane"]),
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
            archive_effect="crash_exemplar",
            reason="invalid terminal run",
        )

    if baseline is None:
        return ScoreExplanation(
            experiment_id=str(experiment["experiment_id"]),
            campaign_id=str(experiment["campaign_id"]),
            lane=str(experiment["lane"]),
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
        archive_effect=_archive_effect_for_disposition(str(experiment["lane"]), decision.disposition),
        reason=decision.reason,
    )


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
    if disposition != "promoted":
        return "unknown"
    if lane == "scout":
        return "advance_to_main"
    if lane == "main":
        return "advance_to_confirm"
    if lane == "confirm":
        return "champion"
    return "unknown"
