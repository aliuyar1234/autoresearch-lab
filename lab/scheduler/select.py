from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

DEFAULT_LANE_MIX: tuple[tuple[str, int], ...] = (("scout", 3), ("main", 2), ("confirm", 1))


class SchedulerSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    family: str
    kind: str
    lane: str
    config_fingerprint: str
    complexity_cost: int
    config_overrides: dict[str, Any]
    priority_hint: int = 0
    validated_anchor_quality: int = 0
    evidence_count: int = 0
    blocked_exhausted_count: int = 0
    novelty_score: float = 0.0


@dataclass(frozen=True)
class HistoryEvent:
    family: str
    crash_class: str | None
    disposition: str | None


def choose_family(
    *,
    has_baseline: bool,
    recent_history: list[dict[str, Any]],
    have_orthogonal_winners_to_combine: bool,
    should_ablate_recent_complex_win: bool,
    novelty_gap: bool,
) -> str:
    history = [
        HistoryEvent(
            family=str(item.get("proposal_family") or item.get("family") or "manual"),
            crash_class=item.get("crash_class"),
            disposition=item.get("disposition"),
        )
        for item in recent_history
    ]
    return choose_next_family(
        has_baseline=has_baseline,
        recent_history=history,
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
    proposals = [
        Proposal(
            proposal_id=str(item["proposal_id"]),
            family=str(item["family"]),
            kind=str(item["kind"]),
            lane=str(item["lane"]),
            config_fingerprint=str(item["config_fingerprint"]),
            complexity_cost=int(item["complexity_cost"]),
            config_overrides=dict(item.get("config_overrides", {})),
            priority_hint=int(item.get("priority_hint", 0)),
            validated_anchor_quality=int(item.get("validated_anchor_quality", 0)),
            evidence_count=len(item.get("evidence", [])),
            blocked_exhausted_count=len(item.get("generation_context", {}).get("blocked_idea_signatures", [])),
            novelty_score=float(item.get("novelty_score", 0.0)),
        )
        for item in proposal_list
    ]
    return rank_queue(proposals, seen_fingerprints=seen_fingerprints)


def choose_next_family(
    *,
    has_baseline: bool,
    recent_history: list[HistoryEvent],
    have_orthogonal_winners_to_combine: bool,
    should_ablate_recent_complex_win: bool,
    novelty_gap: bool,
) -> str:
    if not has_baseline:
        return "baseline"

    recent_crashes = Counter(event.crash_class for event in recent_history if event.crash_class)
    if recent_crashes and recent_crashes.most_common(1)[0][1] >= 3:
        if should_ablate_recent_complex_win:
            return "ablation"
        return "exploit"

    if should_ablate_recent_complex_win:
        return "ablation"
    if have_orthogonal_winners_to_combine:
        return "combine"
    if novelty_gap:
        return "novel"
    return "exploit"


def rank_queue(proposals: list[Proposal], *, seen_fingerprints: set[str]) -> list[Proposal]:
    deduped: list[Proposal] = []
    fingerprints = set(seen_fingerprints)
    for proposal in proposals:
        if proposal.config_fingerprint in fingerprints:
            continue
        fingerprints.add(proposal.config_fingerprint)
        deduped.append(proposal)

    family_rank = {
        "baseline": 0,
        "ablation": 1,
        "combine": 2,
        "exploit": 3,
        "novel": 4,
        "manual": 5,
    }
    lane_rank = {"confirm": 0, "main": 1, "scout": 2}
    return sorted(
        deduped,
        key=lambda proposal: (
            lane_rank.get(proposal.lane, 9),
            family_rank.get(proposal.family, 9),
            -proposal.validated_anchor_quality,
            -proposal.evidence_count,
            proposal.blocked_exhausted_count,
            proposal.complexity_cost,
            -float(proposal.novelty_score),
            -proposal.priority_hint,
            proposal.proposal_id,
        ),
    )


__all__ = [
    "DEFAULT_LANE_MIX",
    "SchedulerSelectionError",
    "choose_family",
    "lane_mix_sequence",
    "rank_structured_queue",
    "select_next_proposal",
]
