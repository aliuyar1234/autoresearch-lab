from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from research.dense_gpt.fingerprint import short_fingerprint, stable_fingerprint
from research.dense_gpt.mutation_rules import apply_path_override
from research.dense_gpt.search_space import estimate_complexity_cost, resolve_dense_config, search_knobs_for_campaign, validate_dense_config

from ..ledger.queries import list_campaign_experiments, list_campaign_proposals, list_memory_records, upsert_proposal
from ..memory import persist_proposal_memory_state, retrieve_memory_context
from ..paths import LabPaths
from ..proposals import normalize_proposal_payload
from ..semantics import is_completed_metric_run, is_pending_validation, is_rankable_experiment, is_validated_promotion
from ..utils import utc_now_iso, write_json
from .compose import disjoint_mergeable, make_ablation_override, make_combine_override
from .exhaustion import compute_idea_signature, is_exhausted_signature, scientific_mutation_paths
from .novelty import novelty_counter
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
    memory_records = list_memory_records(
        connection,
        campaign_id=str(campaign["campaign_id"]),
        comparability_group=str(campaign.get("comparability_group") or ""),
    )
    return generate_structured_proposal_from_state(
        connection=connection,
        paths=paths,
        campaign=campaign,
        lane=lane,
        proposals=proposals,
        experiments=experiments,
        memory_records=memory_records,
        family=family,
        persist=True,
    )


def generate_structured_proposal_from_state(
    *,
    connection=None,
    paths: LabPaths,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    memory_records: list[dict[str, Any]] | None = None,
    family: str | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    attempt_plan = _family_attempt_plan(campaign, lane, proposals, experiments, requested_family=family)
    seen_fingerprints = _existing_fingerprints(proposals)
    memory_records = list(memory_records or [])
    for candidate_family, selector_reason in attempt_plan:
        candidates, blocked_signatures = _generate_family_candidates(
            candidate_family,
            campaign=campaign,
            lane=lane,
            proposals=proposals,
            experiments=experiments,
            seen_fingerprints=seen_fingerprints,
        )
        if not candidates:
            continue
        enriched = [
            _enrich_candidate(
                proposal=candidate,
                campaign=campaign,
                experiments=experiments,
                memory_records=memory_records,
                selector_reason=selector_reason,
                blocked_signatures=blocked_signatures,
                selection_rank=index,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        selected = select_next_proposal(enriched, seen_fingerprints=seen_fingerprints)
        if persist:
            _persist_generated_proposal(paths, selected)
            if connection is not None:
                public_payload = _finalize_generated_payload(selected)
                upsert_proposal(connection, public_payload, updated_at=public_payload["created_at"])
                persist_proposal_memory_state(connection, paths=paths, proposal=selected)
                connection.commit()
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
    memory_records = list_memory_records(
        connection,
        campaign_id=str(campaign["campaign_id"]),
        comparability_group=str(campaign.get("comparability_group") or ""),
    )
    generated: list[dict[str, Any]] = []
    lane_plan = [lane] * count if lane is not None else lane_mix_sequence(count, lane_mix)
    for planned_lane in lane_plan:
        selected = generate_structured_proposal_from_state(
            connection=None,
            paths=paths,
            campaign=campaign,
            lane=planned_lane,
            proposals=proposals,
            experiments=experiments,
            memory_records=memory_records,
            family=family,
            persist=False,
        )
        proposals.append(_proposal_row_like(selected))
        generated.append(selected)
    ranked = rank_structured_queue(generated, seen_fingerprints=set())
    if persist:
        for proposal in ranked:
            _persist_generated_proposal(paths, proposal)
            upsert_proposal(connection, proposal, updated_at=proposal["created_at"])
            persist_proposal_memory_state(connection, paths=paths, proposal=proposal)
        connection.commit()
    return [_finalize_generated_payload(proposal) for proposal in ranked]


def _family_attempt_plan(
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    *,
    requested_family: str | None,
) -> list[tuple[str, str]]:
    if requested_family is not None:
        if requested_family not in FAMILY_CHOICES:
            raise SchedulerGenerationError(f"unsupported family override: {requested_family}")
        return [(requested_family, f"requested family override: {requested_family}")]
    has_baseline = any(_proposal_payload(row).get("family") == "baseline" for row in proposals)
    chosen = choose_family(
        has_baseline=has_baseline,
        recent_history=experiments[:8],
        have_orthogonal_winners_to_combine=_have_combine_parents(experiments),
        should_ablate_recent_complex_win=_have_complex_parent(experiments),
        novelty_gap=_novelty_gap(proposals),
    )
    reasons = {
        "baseline": "no baseline exists yet for this campaign",
        "exploit": "validated or promising anchors exist and the scheduler is compounding around them",
        "ablation": "a recent complex result should be simplified or causally checked",
        "combine": "non-overlapping strong parents exist and should be composed explicitly",
        "novel": "underexplored knobs need fresh search pressure",
    }
    plan = [(chosen, reasons.get(chosen, "scheduler-selected family"))]
    for fallback in ("baseline", "ablation", "combine", "exploit", "novel"):
        if fallback not in {name for name, _ in plan}:
            plan.append((fallback, f"fallback family after {chosen} had no viable candidates"))
    return plan


def _generate_family_candidates(
    family: str,
    *,
    campaign: dict[str, Any],
    lane: str,
    proposals: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    builder = {
        "baseline": _generate_baseline_candidates,
        "exploit": _generate_exploit_candidates,
        "ablation": _generate_ablation_candidates,
        "combine": _generate_combine_candidates,
        "novel": _generate_novel_candidates,
    }.get(family)
    if builder is None:
        return [], []
    return builder(
        campaign=campaign,
        lane=lane,
        proposals=proposals,
        experiments=experiments,
        seen_fingerprints=seen_fingerprints,
        next_counter=_next_proposal_counter(proposals),
    )


def _generate_baseline_candidates(*, campaign: dict[str, Any], lane: str, proposals: list[dict[str, Any]], experiments: list[dict[str, Any]], seen_fingerprints: set[str], next_counter: int) -> tuple[list[dict[str, Any]], list[str]]:
    if any(_proposal_payload(row).get("family") == "baseline" for row in proposals):
        return [], []
    proposal = _build_proposal(
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
        validated_anchor_quality=0,
        novelty_score=0.0,
    )
    return ([proposal] if proposal is not None else []), []


def _generate_exploit_candidates(*, campaign: dict[str, Any], lane: str, proposals: list[dict[str, Any]], experiments: list[dict[str, Any]], seen_fingerprints: set[str], next_counter: int) -> tuple[list[dict[str, Any]], list[str]]:
    anchor = _best_anchor(campaign, experiments)
    if anchor is None:
        return [], []
    return _generate_mutation_candidates(
        campaign=campaign,
        lane=lane,
        family="exploit",
        knobs=_campaign_profile(campaign, lane),
        experiments=experiments,
        seen_fingerprints=seen_fingerprints,
        next_counter=next_counter,
        base_overrides=dict(anchor.get("config_overrides", {})),
        parent_ids=[str(anchor["experiment_id"])],
        expected_direction="improve",
        priority_hint=50,
        validated_anchor_quality=int(anchor["anchor_quality"]),
        novelty_score_for_knob=lambda _knob: 0.0,
        novelty_reason_for_knob=lambda _knob: None,
    )


def _generate_ablation_candidates(*, campaign: dict[str, Any], lane: str, proposals: list[dict[str, Any]], experiments: list[dict[str, Any]], seen_fingerprints: set[str], next_counter: int) -> tuple[list[dict[str, Any]], list[str]]:
    anchor = _recent_complex_anchor(experiments)
    if anchor is None:
        return [], []
    candidates: list[dict[str, Any]] = []
    blocked: set[str] = set()
    counter = next_counter
    for path in list(anchor.get("mutation_paths", [])):
        proposal = _build_proposal(
            campaign=campaign,
            lane=lane,
            family="ablation",
            next_counter=counter,
            config_overrides=make_ablation_override(anchor.get("config_overrides", {}), path),
            complexity_cost=max(0, int(anchor.get("complexity_cost") or 0) - 1),
            hypothesis=f"Ablate `{path}` to test whether the recent complex result really depends on that change.",
            rationale="Ablations should immediately follow complex wins or complex failures so causality stays legible.",
            tags=["ablation", path],
            parent_ids=[str(anchor["experiment_id"])],
            novelty_reason=None,
            priority_hint=80,
            validated_anchor_quality=int(anchor["anchor_quality"]),
            novelty_score=0.0,
        )
        counter += 1
        if _accept_candidate(proposal, family="ablation", campaign_id=str(campaign["campaign_id"]), experiments=experiments, seen_fingerprints=seen_fingerprints, blocked_signatures=blocked, allow_exhausted=True):
            candidates.append(proposal)
    return candidates, sorted(blocked)


def _generate_combine_candidates(*, campaign: dict[str, Any], lane: str, proposals: list[dict[str, Any]], experiments: list[dict[str, Any]], seen_fingerprints: set[str], next_counter: int) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    blocked: set[str] = set()
    counter = next_counter
    strong_anchors = _strong_anchors(campaign, experiments)
    for left, right in _iter_mergeable_anchor_pairs(strong_anchors):
        proposal = _build_proposal(
            campaign=campaign,
            lane=lane,
            family="combine",
            next_counter=counter,
            config_overrides=make_combine_override(dict(left["config_overrides"]), dict(right["config_overrides"])),
            complexity_cost=estimate_complexity_cost(campaign, make_combine_override(dict(left["config_overrides"]), dict(right["config_overrides"]))),
            hypothesis="Combine two distinct strong parents to test whether their gains compose cleanly.",
            rationale="Orthogonal improvements should be merged deliberately and cited explicitly.",
            tags=["combine"],
            parent_ids=[str(left["experiment_id"]), str(right["experiment_id"])],
            novelty_reason=None,
            priority_hint=70,
            validated_anchor_quality=min(int(left["anchor_quality"]), int(right["anchor_quality"])),
            novelty_score=0.0,
            source_experiments=[str(left["experiment_id"]), str(right["experiment_id"])],
        )
        counter += 1
        if _accept_candidate(proposal, family="combine", campaign_id=str(campaign["campaign_id"]), experiments=experiments, seen_fingerprints=seen_fingerprints, blocked_signatures=blocked):
            candidates.append(proposal)
    return candidates, sorted(blocked)


def _generate_novel_candidates(*, campaign: dict[str, Any], lane: str, proposals: list[dict[str, Any]], experiments: list[dict[str, Any]], seen_fingerprints: set[str], next_counter: int) -> tuple[list[dict[str, Any]], list[str]]:
    tag_counts = novelty_counter(_proposal_payload(row).get("config_overrides", {}) for row in proposals)
    anchor = _best_anchor(campaign, experiments)
    base_overrides = dict(anchor.get("config_overrides", {})) if anchor else {}
    ranked_knobs = sorted(_campaign_profile(campaign, lane), key=lambda knob: (tag_counts.get(knob.path, 0), tag_counts.get(knob.tag, 0), knob.path))
    return _generate_mutation_candidates(
        campaign=campaign,
        lane=lane,
        family="novel",
        knobs=ranked_knobs,
        experiments=experiments,
        seen_fingerprints=seen_fingerprints,
        next_counter=next_counter,
        base_overrides=base_overrides,
        parent_ids=[str(anchor["experiment_id"])] if anchor else [],
        expected_direction="exploratory",
        priority_hint=60,
        validated_anchor_quality=int(anchor["anchor_quality"]) if anchor else 0,
        novelty_score_for_knob=lambda knob: max(0.0, 10.0 - float(tag_counts.get(knob.path, 0)) - float(tag_counts.get(knob.tag, 0))),
        novelty_reason_for_knob=lambda knob: f"underexplored knob `{knob.path}`",
        reverse_values=True,
    )


def _generate_mutation_candidates(
    *,
    campaign: dict[str, Any],
    lane: str,
    family: str,
    knobs,
    experiments: list[dict[str, Any]],
    seen_fingerprints: set[str],
    next_counter: int,
    base_overrides: dict[str, Any],
    parent_ids: list[str],
    expected_direction: str,
    priority_hint: int,
    validated_anchor_quality: int,
    novelty_score_for_knob,
    novelty_reason_for_knob,
    reverse_values: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    blocked: set[str] = set()
    counter = next_counter
    for knob in knobs:
        values = reversed(knob.values) if reverse_values else knob.values
        for value in values:
            proposal = _mutated_proposal(
                campaign=campaign,
                lane=lane,
                family=family,
                next_counter=counter,
                base_overrides=base_overrides,
                knob=knob,
                value=value,
                parent_ids=parent_ids,
                complexity_cost=estimate_complexity_cost(campaign, apply_path_override(base_overrides, knob.path, value)),
                expected_direction=expected_direction,
                novelty_reason=novelty_reason_for_knob(knob),
                priority_hint=priority_hint,
                validated_anchor_quality=validated_anchor_quality,
                novelty_score=float(novelty_score_for_knob(knob)),
            )
            counter += 1
            if _accept_candidate(
                proposal,
                family=family,
                campaign_id=str(campaign["campaign_id"]),
                experiments=experiments,
                seen_fingerprints=seen_fingerprints,
                blocked_signatures=blocked,
            ):
                candidates.append(proposal)
                break
    return candidates, sorted(blocked)


def _mutated_proposal(*, campaign: dict[str, Any], lane: str, family: str, next_counter: int, base_overrides: dict[str, Any], knob, value: Any, parent_ids: list[str], complexity_cost: int, expected_direction: str, novelty_reason: str | None, priority_hint: int, validated_anchor_quality: int, novelty_score: float) -> dict[str, Any] | None:
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
        priority_hint=priority_hint,
        validated_anchor_quality=validated_anchor_quality,
        novelty_score=novelty_score,
        expected_direction=expected_direction,
    )


def _build_proposal(*, campaign: dict[str, Any], lane: str, family: str, next_counter: int, config_overrides: dict[str, Any], complexity_cost: int, hypothesis: str, rationale: str, tags: list[str], parent_ids: list[str], novelty_reason: str | None, priority_hint: int, validated_anchor_quality: int, novelty_score: float, expected_direction: str = "improve", source_experiments: list[str] | None = None) -> dict[str, Any] | None:
    resolved_config = resolve_dense_config(campaign, config_overrides)
    if validate_dense_config(campaign, resolved_config):
        return None
    payload = normalize_proposal_payload(
        {
            "proposal_id": f"p_{campaign['campaign_id']}_{family}_{lane}_{next_counter:04d}",
            "campaign_id": campaign["campaign_id"],
            "lane": lane,
            "family": family,
            "kind": "structured",
            "status": "queued",
            "created_at": utc_now_iso(),
            "generator": "scheduler",
            "parent_ids": list(parent_ids),
            "hypothesis": hypothesis,
            "rationale": rationale,
            "config_overrides": config_overrides,
            "complexity_cost": int(max(0, min(9, complexity_cost))),
            "expected_direction": expected_direction,
            "tags": sorted(set(tags + list(scientific_mutation_paths(config_overrides)))),
            "novelty_reason": novelty_reason,
            "notes": None,
            "guardrails": {"max_peak_vram_gb": campaign["runtime"].get("max_peak_vram_gb")},
            "config_fingerprint": short_fingerprint(resolved_config),
            "source_experiments": list(source_experiments or parent_ids),
            "evidence": [],
            "generation_context": {
                "family_selector_reason": "scheduler proposal",
                "anchor_experiment_ids": list(parent_ids),
                "blocked_idea_signatures": [],
                "retrieval_event_id": None,
                "selection_rank": None,
                "selection_score": None,
            },
        }
    )
    payload["priority_hint"] = priority_hint
    payload["validated_anchor_quality"] = int(validated_anchor_quality)
    payload["novelty_score"] = float(novelty_score)
    payload["idea_signature"] = compute_idea_signature(config_overrides)
    payload["mutation_paths"] = scientific_mutation_paths(config_overrides)
    return payload


def _accept_candidate(proposal: dict[str, Any] | None, *, family: str, campaign_id: str, experiments: list[dict[str, Any]], seen_fingerprints: set[str], blocked_signatures: set[str], allow_exhausted: bool = False) -> bool:
    if proposal is None:
        return False
    if _proposal_fingerprint(proposal) in seen_fingerprints:
        return False
    signature = str(proposal.get("idea_signature") or "")
    if not allow_exhausted and family not in {"ablation", "manual"} and is_exhausted_signature(signature, experiments=experiments, campaign_id=campaign_id):
        blocked_signatures.add(signature)
        return False
    return True


def _enrich_candidate(*, proposal: dict[str, Any], campaign: dict[str, Any], experiments: list[dict[str, Any]], memory_records: list[dict[str, Any]], selector_reason: str, blocked_signatures: list[str], selection_rank: int) -> dict[str, Any]:
    enriched = dict(proposal)
    retrieval = retrieve_memory_context(
        memory_records=memory_records,
        campaign_id=str(proposal["campaign_id"]),
        comparability_group=str(campaign.get("comparability_group") or ""),
        proposal_id=str(proposal["proposal_id"]),
        family=str(proposal["family"]),
        lane=str(proposal["lane"]),
        tags=list(proposal.get("tags", [])),
        query_payload={
            "campaign_id": proposal["campaign_id"],
            "comparability_group": campaign.get("comparability_group"),
            "family": proposal["family"],
            "lane": proposal["lane"],
            "proposal_kind": proposal["kind"],
            "tags": proposal.get("tags", []),
            "requested_roles": _requested_roles(str(proposal["family"])),
            "anchor_experiment_ids": list(proposal.get("parent_ids", [])),
            "blocked_signatures": list(blocked_signatures),
            "mutation_paths": list(proposal.get("mutation_paths", [])),
        },
        query_text=f"{proposal['family']} {proposal['lane']} proposal: {proposal['hypothesis']}",
    )
    evidence = list(retrieval.get("evidence", []))
    if str(proposal["family"]) == "combine":
        evidence = _ensure_combine_parent_evidence(evidence=evidence, proposal=proposal, memory_records=memory_records, experiments=experiments)
    retrieval["evidence"] = evidence
    enriched["retrieval_event_id"] = retrieval.get("retrieval_event_id")
    enriched["_retrieval_event"] = retrieval
    enriched["evidence"] = evidence
    enriched["generation_context"] = {
        "family_selector_reason": selector_reason,
        "anchor_experiment_ids": list(proposal.get("parent_ids", [])),
        "blocked_idea_signatures": list(blocked_signatures),
        "retrieval_event_id": retrieval.get("retrieval_event_id"),
        "selection_rank": selection_rank,
        "selection_score": round(sum(float(item.get("score") or 0.0) for item in evidence), 6) if evidence else None,
    }
    return normalize_proposal_payload(enriched)


def _ensure_combine_parent_evidence(*, evidence: list[dict[str, Any]], proposal: dict[str, Any], memory_records: list[dict[str, Any]], experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_memory_id = {str(item["memory_id"]): dict(item) for item in evidence}
    for parent_id in list(proposal.get("parent_ids", []))[:2]:
        record = _memory_record_for_parent(parent_id, memory_records=memory_records, experiments=experiments)
        if record is None:
            continue
        by_memory_id[str(record["memory_id"])] = {
            "memory_id": str(record["memory_id"]),
            "record_type": str(record["record_type"]),
            "role": "combination_parent",
            "score": max(9.0, float(record.get("score") or 0.0)),
            "reason": "selected as an explicit combination parent",
            "source_ref": str(record["source_ref"]),
        }
    ordered = list(by_memory_id.values())
    ordered.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item["memory_id"])))
    return ordered[:4]


def _memory_record_for_parent(parent_id: str, *, memory_records: list[dict[str, Any]], experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in memory_records:
        if str(record.get("source_ref") or "") == parent_id and record.get("record_type") in {"champion_snapshot", "experiment_result"}:
            return record
    experiment = next((row for row in experiments if str(row["experiment_id"]) == parent_id), None)
    if experiment is None:
        return None
    payload = _proposal_payload(experiment)
    return {
        "memory_id": f"synthetic_{parent_id}",
        "record_type": "experiment_result",
        "source_ref": parent_id,
        "score": 9.0,
        "payload": {"config_overrides": payload.get("config_overrides", {})},
    }


def _requested_roles(family: str) -> list[str]:
    if family == "combine":
        return ["combination_parent", "warning", "supporting_precedent"]
    if family == "novel":
        return ["warning", "report_note", "supporting_precedent"]
    if family == "ablation":
        return ["warning", "supporting_precedent"]
    return ["supporting_precedent", "warning"]


def _campaign_profile(campaign: dict[str, Any], lane: str):
    return search_knobs_for_campaign(campaign, lane)


def _existing_fingerprints(proposals: Iterable[dict[str, Any]]) -> set[str]:
    fingerprints: set[str] = set()
    for row in proposals:
        payload = _proposal_payload(row)
        if isinstance(payload.get("config_fingerprint"), str) and payload.get("config_fingerprint"):
            fingerprints.add(str(payload["config_fingerprint"]))
            continue
        fingerprints.add(stable_fingerprint(payload.get("config_overrides", {})))
    return fingerprints


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if raw:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return normalize_proposal_payload(payload)
    return normalize_proposal_payload(
        {
            "proposal_id": row.get("proposal_id") or "unknown",
            "campaign_id": row.get("campaign_id") or "unknown",
            "lane": row.get("lane") or "scout",
            "family": row.get("family") or "manual",
            "kind": row.get("kind") or "manual",
            "status": row.get("status") or "queued",
            "created_at": row.get("created_at") or utc_now_iso(),
            "generator": row.get("generator") or "manual",
            "parent_ids": json.loads(row.get("parent_ids_json") or "[]"),
            "hypothesis": row.get("hypothesis") or "generated proposal",
            "rationale": row.get("rationale") or "generated proposal",
            "config_fingerprint": row.get("config_fingerprint"),
            "config_overrides": json.loads(row.get("config_overrides_json") or "{}"),
            "complexity_cost": int(row.get("complexity_cost") or 0),
            "expected_direction": "improve",
            "tags": [],
            "evidence": [],
            "generation_context": {
                "family_selector_reason": "existing proposal row",
                "anchor_experiment_ids": [],
                "blocked_idea_signatures": [],
                "retrieval_event_id": row.get("retrieval_event_id"),
                "selection_rank": None,
                "selection_score": None,
            },
        }
    )


def _best_anchor(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    completed = [_anchor_from_experiment(row) for row in experiments if is_completed_metric_run(row)]
    return sorted(completed, key=lambda row: _anchor_sort_key(campaign, row))[0] if completed else None


def _strong_anchors(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors = [_anchor_from_experiment(row) for row in experiments if is_completed_metric_run(row)]
    strong = [row for row in anchors if int(row.get("anchor_quality") or 0) >= 2]
    return sorted(strong, key=lambda row: _anchor_sort_key(campaign, row))[:6]


def _recent_complex_anchor(experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in experiments:
        if not is_completed_metric_run(row):
            continue
        anchor = _anchor_from_experiment(row)
        if int(anchor.get("complexity_cost") or 0) < 2 or not anchor.get("config_overrides"):
            continue
        if int(anchor.get("anchor_quality") or 0) >= 2 or str(anchor.get("validation_state") or "") == "failed":
            return anchor
    return None


def _have_complex_parent(experiments: list[dict[str, Any]]) -> bool:
    return _recent_complex_anchor(experiments) is not None


def _have_combine_parents(experiments: list[dict[str, Any]]) -> bool:
    eligible = [row for row in (_anchor_from_experiment(item) for item in experiments if is_completed_metric_run(item)) if int(row.get("anchor_quality") or 0) >= 2]
    return any(True for _left, _right in _iter_mergeable_anchor_pairs(eligible))


def _iter_mergeable_anchor_pairs(anchors: list[dict[str, Any]]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for index, left in enumerate(anchors):
        for right in anchors[index + 1 :]:
            if not left.get("config_overrides") or not right.get("config_overrides"):
                continue
            if set(left.get("mutation_paths", [])) & set(right.get("mutation_paths", [])):
                continue
            if disjoint_mergeable(dict(left["config_overrides"]), dict(right["config_overrides"])):
                yield left, right


def _anchor_from_experiment(row: dict[str, Any]) -> dict[str, Any]:
    payload = _proposal_payload(row)
    return {
        "experiment_id": row["experiment_id"],
        "proposal_id": row.get("proposal_id"),
        "primary_metric_value": float(row["primary_metric_value"]) if row.get("primary_metric_value") is not None else None,
        "complexity_cost": payload.get("complexity_cost", row.get("complexity_cost") or 0),
        "config_overrides": payload.get("config_overrides", {}),
        "mutation_paths": payload.get("mutation_paths", []),
        "idea_signature": row.get("idea_signature") or payload.get("idea_signature"),
        "family": payload.get("family", row.get("proposal_family")),
        "disposition": row.get("disposition"),
        "validation_state": row.get("validation_state"),
        "anchor_quality": _anchor_quality(row),
    }


def _anchor_quality(row: dict[str, Any]) -> int:
    if is_validated_promotion(row):
        return 4
    if is_pending_validation(row):
        return 3
    if str(row.get("disposition") or "") == "archived":
        return 2
    if is_completed_metric_run(row) and is_rankable_experiment(row):
        return 1
    return 0


def _anchor_sort_key(campaign: dict[str, Any], row: dict[str, Any]) -> tuple[Any, ...]:
    metric_value = float(row.get("primary_metric_value") or 0.0)
    metric_key = -metric_value if str(campaign["primary_metric"]["direction"]) == "max" else metric_value
    return (-int(row.get("anchor_quality") or 0), metric_key, int(row.get("complexity_cost") or 0), str(row.get("experiment_id") or ""))


def _novelty_gap(proposals: list[dict[str, Any]]) -> bool:
    if len(proposals) < 3:
        return False
    return len(novelty_counter(_proposal_payload(row).get("config_overrides", {}) for row in proposals)) < 4


def _proposal_fingerprint(proposal: dict[str, Any]) -> str:
    if isinstance(proposal.get("config_fingerprint"), str) and proposal.get("config_fingerprint"):
        return str(proposal["config_fingerprint"])
    return stable_fingerprint(proposal.get("config_overrides", {}))


def _next_proposal_counter(proposals: list[dict[str, Any]]) -> int:
    pattern = re.compile(r"_(\d{4,})$")
    current = 0
    for row in proposals:
        match = pattern.search(str(row.get("proposal_id") or ""))
        if match:
            current = max(current, int(match.group(1)))
    return current + 1


def _persist_generated_proposal(paths: LabPaths, proposal: dict[str, Any]) -> Path:
    proposal_path = paths.proposals_root / f"{proposal['proposal_id']}.json"
    write_json(proposal_path, _finalize_generated_payload(proposal))
    return proposal_path


def _proposal_row_like(payload: dict[str, Any]) -> dict[str, Any]:
    public_payload = _finalize_generated_payload(payload)
    return {
        "proposal_id": public_payload["proposal_id"],
        "campaign_id": public_payload["campaign_id"],
        "lane": public_payload["lane"],
        "family": public_payload["family"],
        "kind": public_payload["kind"],
        "status": public_payload["status"],
        "generator": public_payload["generator"],
        "created_at": public_payload["created_at"],
        "proposal_json": json.dumps(public_payload, sort_keys=True),
        "config_overrides_json": json.dumps(public_payload.get("config_overrides", {}), sort_keys=True),
    }


def _finalize_generated_payload(payload: dict[str, Any]) -> dict[str, Any]:
    finalized = normalize_proposal_payload(payload)
    for key in ("_retrieval_event", "priority_hint", "validated_anchor_quality", "novelty_score"):
        finalized.pop(key, None)
    return finalized


__all__ = ["DEFAULT_LANE_MIX", "FAMILY_CHOICES", "SchedulerGenerationError", "generate_structured_proposal", "generate_structured_proposal_from_state", "plan_structured_queue"]
