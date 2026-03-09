from __future__ import annotations

from typing import Any, Iterable

from reference_impl.scheduler_policy import HistoryEvent, Proposal, choose_next_family, rank_queue

DEFAULT_LANE_MIX: tuple[tuple[str, int], ...] = (("scout", 3), ("main", 2), ("confirm", 1))


class SchedulerSelectionError(ValueError):
    pass


def choose_family(
    *,
    has_baseline: bool,
    recent_history: list[dict[str, Any]],
    have_orthogonal_winners_to_combine: bool,
    should_ablate_recent_complex_win: bool,
    novelty_gap: bool,
) -> str:
    return choose_next_family(
        has_baseline=has_baseline,
        recent_history=[
            HistoryEvent(
                family=str(item.get("proposal_family") or item.get("family") or "manual"),
                crash_class=item.get("crash_class"),
                disposition=item.get("disposition"),
            )
            for item in recent_history
        ],
        have_orthogonal_winners_to_combine=have_orthogonal_winners_to_combine,
        should_ablate_recent_complex_win=should_ablate_recent_complex_win,
        novelty_gap=novelty_gap,
    )


def select_next_proposal(candidates: Iterable[dict[str, Any]], *, seen_fingerprints: set[str]) -> dict[str, Any]:
    proposal_list = list(candidates)
    ranked = _rank_proposals(proposal_list, seen_fingerprints=seen_fingerprints)
    if not ranked:
        raise SchedulerSelectionError("no selectable proposals remained after dedupe")
    by_id = {str(item["proposal_id"]): item for item in proposal_list}
    return by_id[ranked[0].proposal_id]


def rank_structured_queue(candidates: Iterable[dict[str, Any]], *, seen_fingerprints: set[str]) -> list[dict[str, Any]]:
    proposal_list = list(candidates)
    ranked = _rank_proposals(proposal_list, seen_fingerprints=seen_fingerprints)
    by_id = {str(item["proposal_id"]): item for item in proposal_list}
    return [by_id[item.proposal_id] for item in ranked]


def lane_mix_sequence(count: int, lane_mix: tuple[tuple[str, int], ...] = DEFAULT_LANE_MIX) -> list[str]:
    sequence: list[str] = []
    while len(sequence) < count:
        for lane, weight in lane_mix:
            sequence.extend([lane] * max(0, weight))
            if len(sequence) >= count:
                return sequence[:count]
    return sequence[:count]


def _rank_proposals(proposal_list: list[dict[str, Any]], *, seen_fingerprints: set[str]) -> list[Proposal]:
    return rank_queue(
        [
            Proposal(
                proposal_id=str(item["proposal_id"]),
                family=str(item["family"]),
                kind=str(item["kind"]),
                lane=str(item["lane"]),
                config_fingerprint=str(item["config_fingerprint"]),
                complexity_cost=int(item["complexity_cost"]),
                config_overrides=dict(item.get("config_overrides", {})),
                priority_hint=int(item.get("priority_hint", 0)),
            )
            for item in proposal_list
        ],
        seen_fingerprints=seen_fingerprints,
    )


__all__ = [
    "DEFAULT_LANE_MIX",
    "SchedulerSelectionError",
    "choose_family",
    "lane_mix_sequence",
    "rank_structured_queue",
    "select_next_proposal",
]
