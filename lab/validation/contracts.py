from __future__ import annotations

from dataclasses import asdict, dataclass


REVIEW_MODE_TO_SPLIT = {
    "confirm": "search_val",
    "audit": "audit_val",
    "locked": "locked_val",
}

REVIEW_MODE_TO_RUN_PURPOSE = {
    "confirm": "confirm",
    "audit": "audit",
    "locked": "audit",
}


@dataclass(frozen=True)
class ReviewRunRecord:
    experiment_id: str
    replay_source_experiment_id: str
    seed: int
    metric_value: float
    summary_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReviewResult:
    review_id: str
    source_experiment_id: str
    campaign_id: str
    review_type: str
    eval_split: str
    candidate_experiment_ids: list[str]
    comparator_experiment_ids: list[str]
    seed_list: list[int]
    decision: str
    reason: str
    candidate_metric_median: float | None
    comparator_metric_median: float | None
    delta_median: float | None
    review: dict[str, object]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NoiseProbeResult:
    campaign_id: str
    lane: str
    count: int
    metric_values: list[float]
    metric_median: float | None
    metric_min: float | None
    metric_max: float | None
    metric_range: float | None
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

