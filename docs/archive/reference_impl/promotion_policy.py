from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class Thresholds:
    scout_to_main_min_delta: float
    main_to_confirm_min_delta: float
    champion_min_delta: float
    tie_threshold: float
    allow_complexity_tie_break: bool = True


@dataclasses.dataclass(frozen=True)
class Candidate:
    metric_value: float
    complexity_cost: int
    audit_ok: bool = True
    confirm_ok: bool = True
    review_required: bool = False
    comparable: bool = True
    valid: bool = True


@dataclasses.dataclass(frozen=True)
class Decision:
    disposition: str
    reason: str


def _improvement(direction: str, baseline: float, candidate: float) -> float:
    if direction == "min":
        return baseline - candidate
    if direction == "max":
        return candidate - baseline
    raise ValueError(f"unsupported direction: {direction}")


def decide_lane_promotion(
    *,
    lane: str,
    direction: str,
    baseline_metric: float,
    candidate: Candidate,
    thresholds: Thresholds,
) -> Decision:
    if not candidate.valid:
        return Decision("failed", "invalid terminal run")
    if not candidate.comparable:
        return Decision("discarded", "not comparable")

    delta = _improvement(direction, baseline_metric, candidate.metric_value)

    if lane == "scout":
        needed = thresholds.scout_to_main_min_delta
        if delta >= needed:
            return Decision("promoted", f"scout improvement {delta:.6f} >= {needed:.6f}")
        return Decision("discarded", f"scout improvement {delta:.6f} < {needed:.6f}")

    if lane == "main":
        needed = thresholds.main_to_confirm_min_delta
        if delta >= needed:
            return Decision("promoted", f"main improvement {delta:.6f} >= {needed:.6f}")
        if thresholds.allow_complexity_tie_break and abs(delta) <= thresholds.tie_threshold and candidate.complexity_cost <= 1:
            return Decision("archived", "main nearly tied but simpler")
        return Decision("discarded", f"main improvement {delta:.6f} < {needed:.6f}")

    if lane == "confirm":
        needed = thresholds.champion_min_delta
        if not candidate.audit_ok or not candidate.confirm_ok:
            return Decision("discarded", "confirm candidate failed audit or confirm checks")
        if delta >= needed:
            if candidate.review_required:
                return Decision("pending_validation", f"champion improvement {delta:.6f} >= {needed:.6f}; pending validation review")
            return Decision("promoted", f"champion improvement {delta:.6f} >= {needed:.6f}")
        if thresholds.allow_complexity_tie_break and abs(delta) <= thresholds.tie_threshold and candidate.complexity_cost <= 1:
            return Decision("archived", "confirm nearly tied but simpler")
        return Decision("archived", f"confirm improvement {delta:.6f} < {needed:.6f}")

    raise ValueError(f"unsupported lane: {lane}")
