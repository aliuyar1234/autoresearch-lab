from __future__ import annotations

import dataclasses
from collections import Counter
from copy import deepcopy
from typing import Any


@dataclasses.dataclass(frozen=True)
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


@dataclasses.dataclass(frozen=True)
class HistoryEvent:
    family: str
    crash_class: str | None
    disposition: str | None


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

    recent_crashes = Counter(ev.crash_class for ev in recent_history if ev.crash_class)
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
    deduped = []
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
        key=lambda p: (
            lane_rank.get(p.lane, 9),
            family_rank.get(p.family, 9),
            -p.validated_anchor_quality,
            -p.evidence_count,
            p.blocked_exhausted_count,
            p.complexity_cost,
            -float(p.novelty_score),
            -p.priority_hint,
            p.proposal_id,
        ),
    )


def merge_nested_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(left)
    for key, value in right.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge_nested_dicts(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def flatten_override_paths(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for key, value in sorted(payload.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.extend(flatten_override_paths(value, path))
        else:
            items.append((path, value))
    return items


def unflatten_override_paths(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in items:
        cursor = out
        parts = path.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return out


def make_ablation_override(parent_overrides: dict[str, Any], remove_path: str) -> dict[str, Any]:
    items = [(path, value) for path, value in flatten_override_paths(parent_overrides) if path != remove_path]
    return unflatten_override_paths(items)


def disjoint_mergeable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_paths = {path for path, _ in flatten_override_paths(left)}
    right_paths = {path for path, _ in flatten_override_paths(right)}
    return left_paths.isdisjoint(right_paths)


def make_combine_override(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if not disjoint_mergeable(left, right):
        raise ValueError("combine only supports disjoint override paths in the reference implementation")
    return merge_nested_dicts(left, right)


def novelty_tags(config_overrides: dict[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []
    flat = flatten_override_paths(config_overrides)
    for path, value in flat:
        tags.append(path)
        if isinstance(value, (int, float)):
            magnitude = "small" if abs(float(value)) < 2 else "large"
            tags.append(f"{path}:{magnitude}")
        else:
            tags.append(f"{path}:{value}")
    return tuple(sorted(set(tags)))
