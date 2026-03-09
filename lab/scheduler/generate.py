from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from research.dense_gpt.fingerprint import short_fingerprint, stable_fingerprint
from research.dense_gpt.mutation_rules import apply_path_override
from research.dense_gpt.search_space import estimate_complexity_cost, resolve_dense_config, search_knobs_for_campaign, validate_dense_config

from ..ledger.queries import list_campaign_experiments, list_campaign_proposals
from ..paths import LabPaths
from ..utils import utc_now_iso, write_json
from .compose import disjoint_mergeable, flatten_override_paths, make_ablation_override, make_combine_override, merge_nested_dicts
from .novelty import novelty_counter, novelty_tags
from .select import DEFAULT_LANE_MIX, choose_family, lane_mix_sequence, rank_structured_queue, select_next_proposal

FAMILY_CHOICES = ("baseline", "exploit", "ablation", "combine", "novel", "manual")


class SchedulerGenerationError(ValueError):
    pass


def generate_structured_proposal(
    connection,
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    lane: str,
    family: str | None = None,
) -> dict[str, Any]:
    proposals = list_campaign_proposals(connection, str(campaign["campaign_id"]))
    experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
    return generate_structured_proposal_from_state(
        paths=paths,
        campaign=campaign,
        lane=lane,
        proposals=proposals,
        experiments=experiments,
        family=family,
        persist=True,
    )


def generate_structured_proposal_from_state(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    family: str | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    attempt_order = _family_attempt_order(campaign, lane, proposals, experiments, requested_family=family)
    seen_fingerprints = _existing_fingerprints(proposals)

    for candidate_family in attempt_order:
        candidates = _generate_family_candidates(
            candidate_family,
            campaign=campaign,
            lane=lane,
            proposals=proposals,
            experiments=experiments,
            seen_fingerprints=seen_fingerprints,
        )
        if not candidates:
            continue
        selected = select_next_proposal(candidates, seen_fingerprints=seen_fingerprints)
        if persist:
            _persist_generated_proposal(paths, selected)
        return _finalize_generated_payload(selected)

    if family:
        raise SchedulerGenerationError(f"could not generate a {family} structured proposal for {campaign['campaign_id']}:{lane}")
    raise SchedulerGenerationError(f"could not generate any structured proposal for {campaign['campaign_id']}:{lane}")


def plan_structured_queue(
    connection,
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    count: int,
    lane: str | None = None,
    family: str | None = None,
    lane_mix: tuple[tuple[str, int], ...] = DEFAULT_LANE_MIX,
    persist: bool = False,
) -> list[dict[str, Any]]:
    if count < 1:
        return []

    proposals = list_campaign_proposals(connection, str(campaign["campaign_id"]))
    experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
    generated: list[dict[str, Any]] = []
    lane_plan = [lane] * count if lane is not None else lane_mix_sequence(count, lane_mix)

    for planned_lane in lane_plan:
        selected = generate_structured_proposal_from_state(
            paths=paths,
            campaign=campaign,
            lane=planned_lane,
            proposals=proposals,
            experiments=experiments,
            family=family,
            persist=False,
        )
        proposals.append(_proposal_row_like(selected))
        generated.append(selected)

    ranked = rank_structured_queue(generated, seen_fingerprints=set())
    if persist:
        for proposal in ranked:
            _persist_generated_proposal(paths, proposal)
    return [_finalize_generated_payload(proposal) for proposal in ranked]


def _family_attempt_order(
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    *,
    requested_family: str | None,
) -> list[str]:
    if requested_family is not None:
        if requested_family not in FAMILY_CHOICES:
            raise SchedulerGenerationError(f"unsupported family override: {requested_family}")
        return [requested_family]

    has_baseline = any(_proposal_payload(row).get("family") == "baseline" for row in proposals)
    recent_history = experiments[:8]
    chosen = choose_family(
        has_baseline=has_baseline,
        recent_history=recent_history,
        have_orthogonal_winners_to_combine=_have_combine_parents(experiments),
        should_ablate_recent_complex_win=_have_complex_parent(experiments),
        novelty_gap=_novelty_gap(proposals),
    )
    order = [chosen]
    for family in ("baseline", "ablation", "combine", "exploit", "novel"):
        if family not in order:
            order.append(family)
    return order


def _generate_family_candidates(
    family: str,
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
) -> list[dict[str, Any]]:
    builder = {
        "baseline": _generate_baseline_candidates,
        "exploit": _generate_exploit_candidates,
        "ablation": _generate_ablation_candidates,
        "combine": _generate_combine_candidates,
        "novel": _generate_novel_candidates,
    }.get(family)
    if builder is None:
        return []
    next_counter = _next_proposal_counter(proposals)
    return builder(
        campaign=campaign,
        lane=lane,
        proposals=proposals,
        experiments=experiments,
        seen_fingerprints=seen_fingerprints,
        next_counter=next_counter,
    )


def _generate_baseline_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
) -> list[dict[str, Any]]:
    if any(_proposal_payload(row).get("family") == "baseline" for row in proposals):
        return []
    return [
        _build_proposal(
            campaign=campaign,
            lane=lane,
            family="baseline",
            next_counter=next_counter,
            config_overrides={},
            complexity_cost=0,
            hypothesis="Establish the campaign baseline before mutating the search space.",
            rationale="The scheduler should always preserve one clean comparable reference run.",
            tags=["baseline"],
            parent_ids=[],
            novelty_reason=None,
            priority_hint=100,
        )
    ]


def _generate_exploit_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
) -> list[dict[str, Any]]:
    anchor = _best_anchor(campaign, experiments)
    if anchor is None:
        return []
    base_overrides = dict(anchor.get("config_overrides", {}))
    candidates: list[dict[str, Any]] = []
    counter = next_counter
    for knob in _campaign_profile(campaign, lane):
        for value in knob.values:
            proposal = _mutated_proposal(
                campaign=campaign,
                lane=lane,
                family="exploit",
                next_counter=counter,
                base_overrides=base_overrides,
                knob=knob,
                value=value,
                parent_ids=[str(anchor["experiment_id"])],
                complexity_cost=estimate_complexity_cost(campaign, apply_path_override(base_overrides, knob.path, value)),
                expected_direction="improve",
                novelty_reason=None,
                priority_hint=50,
            )
            counter += 1
            if proposal is None:
                continue
            if _proposal_fingerprint(proposal) in seen_fingerprints:
                continue
            candidates.append(proposal)
            break
    return candidates


def _generate_ablation_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
) -> list[dict[str, Any]]:
    anchor = _recent_complex_anchor(experiments)
    if anchor is None:
        return []
    flat_paths = flatten_override_paths(anchor.get("config_overrides", {}))
    if not flat_paths:
        return []
    candidates: list[dict[str, Any]] = []
    counter = next_counter
    for path, _ in flat_paths:
        new_overrides = make_ablation_override(anchor.get("config_overrides", {}), path)
        proposal = _build_proposal(
            campaign=campaign,
            lane=lane,
            family="ablation",
            next_counter=counter,
            config_overrides=new_overrides,
            complexity_cost=max(0, int(anchor.get("complexity_cost") or 0) - 1),
            hypothesis=f"Ablate `{path}` to test whether the recent win depends on that change.",
            rationale="Ablations should immediately follow complex wins so causality remains legible.",
            tags=["ablation", path],
            parent_ids=[str(anchor["experiment_id"])],
            novelty_reason=None,
            priority_hint=80,
        )
        counter += 1
        if proposal is None:
            continue
        if _proposal_fingerprint(proposal) in seen_fingerprints:
            continue
        candidates.append(proposal)
    return candidates


def _generate_combine_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
) -> list[dict[str, Any]]:
    strong_anchors = _strong_anchors(campaign, experiments)
    candidates: list[dict[str, Any]] = []
    counter = next_counter
    for index, left in enumerate(strong_anchors):
        for right in strong_anchors[index + 1 :]:
            left_overrides = dict(left.get("config_overrides", {}))
            right_overrides = dict(right.get("config_overrides", {}))
            if not left_overrides or not right_overrides or not disjoint_mergeable(left_overrides, right_overrides):
                continue
            merged = make_combine_override(left_overrides, right_overrides)
            proposal = _build_proposal(
                campaign=campaign,
                lane=lane,
                family="combine",
                next_counter=counter,
                config_overrides=merged,
                complexity_cost=estimate_complexity_cost(campaign, merged),
                hypothesis="Combine two non-overlapping structured wins to test whether their gains compose.",
                rationale="Orthogonal improvements should be merged explicitly rather than assumed to compose.",
                tags=["combine"],
                parent_ids=[str(left["experiment_id"]), str(right["experiment_id"])],
                novelty_reason=None,
                priority_hint=70,
            )
            counter += 1
            if proposal is None:
                continue
            if _proposal_fingerprint(proposal) in seen_fingerprints:
                continue
            candidates.append(proposal)
    return candidates


def _generate_novel_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
) -> list[dict[str, Any]]:
    tag_counts = novelty_counter(_proposal_payload(row).get("config_overrides", {}) for row in proposals)
    anchor = _best_anchor(campaign, experiments)
    base_overrides = dict(anchor.get("config_overrides", {})) if anchor else {}
    ranked_knobs = sorted(
        _campaign_profile(campaign, lane),
        key=lambda knob: (tag_counts.get(knob.path, 0), tag_counts.get(knob.tag, 0), knob.path),
    )
    candidates: list[dict[str, Any]] = []
    counter = next_counter
    for knob in ranked_knobs:
        for value in reversed(knob.values):
            proposal = _mutated_proposal(
                campaign=campaign,
                lane=lane,
                family="novel",
                next_counter=counter,
                base_overrides=base_overrides,
                knob=knob,
                value=value,
                parent_ids=[str(anchor["experiment_id"])] if anchor else [],
                complexity_cost=estimate_complexity_cost(campaign, apply_path_override(base_overrides, knob.path, value)),
                expected_direction="exploratory",
                novelty_reason=f"underexplored knob `{knob.path}`",
                priority_hint=60,
            )
            counter += 1
            if proposal is None:
                continue
            if _proposal_fingerprint(proposal) in seen_fingerprints:
                continue
            candidates.append(proposal)
            break
    return candidates


def _mutated_proposal(
    *,
    campaign: dict[str, Any],
    lane: str,
    family: str,
    next_counter: int,
    base_overrides: dict[str, Any],
    knob: SearchKnob,
    value: Any,
    parent_ids: list[str],
    complexity_cost: int,
    expected_direction: str,
    novelty_reason: str | None,
    priority_hint: int,
) -> dict[str, Any]:
    mutated = apply_path_override(base_overrides, knob.path, value)
    return _build_proposal(
        campaign=campaign,
        lane=lane,
        family=family,
        next_counter=next_counter,
        config_overrides=mutated,
        complexity_cost=complexity_cost,
        hypothesis=knob.hypothesis,
        rationale=knob.rationale,
        tags=[family, knob.tag],
        parent_ids=parent_ids,
        novelty_reason=novelty_reason,
        expected_direction=expected_direction,
        priority_hint=priority_hint,
    )


def _build_proposal(
    *,
    campaign: dict[str, Any],
    lane: str,
    family: str,
    next_counter: int,
    config_overrides: dict[str, Any],
    complexity_cost: int,
    hypothesis: str,
    rationale: str,
    tags: list[str],
    parent_ids: list[str],
    novelty_reason: str | None,
    priority_hint: int,
    expected_direction: str = "improve",
) -> dict[str, Any] | None:
    resolved_config = resolve_dense_config(campaign, config_overrides)
    if validate_dense_config(campaign, resolved_config):
        return None
    proposal_id = f"p_{campaign['campaign_id']}_{family}_{lane}_{next_counter:04d}"
    payload = {
        "proposal_id": proposal_id,
        "campaign_id": campaign["campaign_id"],
        "lane": lane,
        "family": family,
        "kind": "structured",
        "status": "queued",
        "created_at": utc_now_iso(),
        "generator": "scheduler",
        "parent_ids": parent_ids,
        "hypothesis": hypothesis,
        "rationale": rationale,
        "config_overrides": config_overrides,
        "complexity_cost": int(max(0, min(9, estimate_complexity_cost(campaign, config_overrides)))),
        "expected_direction": expected_direction,
        "tags": sorted(set(tags)),
        "novelty_reason": novelty_reason,
        "notes": None,
        "guardrails": {
            "max_peak_vram_gb": campaign["runtime"].get("max_peak_vram_gb"),
        },
        "config_fingerprint": short_fingerprint(resolved_config),
        "priority_hint": priority_hint,
    }
    return payload


def _campaign_profile(campaign: dict[str, Any], lane: str):
    return search_knobs_for_campaign(campaign, lane)


def _existing_fingerprints(proposals: Iterable[dict[str, Any]]) -> set[str]:
    fingerprints: set[str] = set()
    for row in proposals:
        payload = _proposal_payload(row)
        config_fingerprint = payload.get("config_fingerprint")
        if isinstance(config_fingerprint, str) and config_fingerprint:
            fingerprints.add(config_fingerprint)
            continue
        config_overrides = payload.get("config_overrides", {})
        if not isinstance(config_overrides, dict):
            continue
        fingerprints.add(stable_fingerprint(config_overrides))
    return fingerprints


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        raw = row.get("proposal_json".upper())
    if raw:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    raw_overrides = row.get("config_overrides_json")
    overrides = json.loads(raw_overrides) if raw_overrides else {}
    return {
        "proposal_id": row.get("proposal_id"),
        "family": row.get("family"),
        "kind": row.get("kind"),
        "config_fingerprint": row.get("config_fingerprint"),
        "config_overrides": overrides if isinstance(overrides, dict) else {},
    }


def _best_anchor(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    direction = str(campaign["primary_metric"]["direction"])
    completed = [
        _anchor_from_experiment(row)
        for row in experiments
        if row.get("status") == "completed" and row.get("primary_metric_value") is not None
    ]
    if not completed:
        return None
    reverse = direction == "max"
    return sorted(
        completed,
        key=lambda row: (
            float(row["primary_metric_value"]),
            int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=reverse,
    )[0]


def _strong_anchors(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [
        _anchor_from_experiment(row)
        for row in experiments
        if row.get("status") == "completed" and row.get("primary_metric_value") is not None
    ]
    direction = str(campaign["primary_metric"]["direction"])
    return sorted(
        completed,
        key=lambda row: (
            float(row["primary_metric_value"]),
            int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=direction == "max",
    )[:5]


def _recent_complex_anchor(experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in experiments:
        if row.get("status") != "completed":
            continue
        anchor = _anchor_from_experiment(row)
        if int(anchor.get("complexity_cost") or 0) >= 2 and anchor.get("config_overrides"):
            return anchor
    return None


def _have_complex_parent(experiments: list[dict[str, Any]]) -> bool:
    return _recent_complex_anchor(experiments) is not None


def _have_combine_parents(experiments: list[dict[str, Any]]) -> bool:
    anchors = [_anchor_from_experiment(row) for row in experiments if row.get("status") == "completed"]
    for index, left in enumerate(anchors):
        for right in anchors[index + 1 :]:
            if left.get("config_overrides") and right.get("config_overrides") and disjoint_mergeable(
                dict(left["config_overrides"]),
                dict(right["config_overrides"]),
            ):
                return True
    return False


def _anchor_from_experiment(row: dict[str, Any]) -> dict[str, Any]:
    payload = _proposal_payload(row)
    return {
        "experiment_id": row["experiment_id"],
        "proposal_id": row.get("proposal_id"),
        "primary_metric_value": row.get("primary_metric_value"),
        "complexity_cost": payload.get("complexity_cost", row.get("complexity_cost") or 0),
        "config_overrides": payload.get("config_overrides", {}),
        "family": payload.get("family", row.get("proposal_family")),
        "disposition": row.get("disposition"),
    }


def _novelty_gap(proposals: list[dict[str, Any]]) -> bool:
    if len(proposals) < 3:
        return False
    counts = novelty_counter(_proposal_payload(row).get("config_overrides", {}) for row in proposals)
    return len(counts) < 4


def _proposal_fingerprint(proposal: dict[str, Any]) -> str:
    config_fingerprint = proposal.get("config_fingerprint")
    if isinstance(config_fingerprint, str) and config_fingerprint:
        return config_fingerprint
    return stable_fingerprint(proposal.get("config_overrides", {}))


def _next_proposal_counter(proposals: list[dict[str, Any]]) -> int:
    pattern = re.compile(r"_(\d{4,})$")
    current = 0
    for row in proposals:
        proposal_id = str(row.get("proposal_id") or "")
        match = pattern.search(proposal_id)
        if not match:
            continue
        current = max(current, int(match.group(1)))
    return current + 1


def _persist_generated_proposal(paths: LabPaths, proposal: dict[str, Any]) -> Path:
    proposal_path = paths.proposals_root / f"{proposal['proposal_id']}.json"
    payload = dict(proposal)
    payload.pop("priority_hint", None)
    write_json(proposal_path, payload)
    proposal.pop("priority_hint", None)
    return proposal_path


def _proposal_row_like(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": payload["proposal_id"],
        "family": payload["family"],
        "kind": payload["kind"],
        "proposal_json": json.dumps(payload, sort_keys=True),
        "config_overrides_json": json.dumps(payload.get("config_overrides", {}), sort_keys=True),
    }


def _finalize_generated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    finalized = dict(payload)
    finalized.pop("priority_hint", None)
    return finalized


__all__ = [
    "DEFAULT_LANE_MIX",
    "FAMILY_CHOICES",
    "SchedulerGenerationError",
    "generate_structured_proposal",
    "generate_structured_proposal_from_state",
    "plan_structured_queue",
]
