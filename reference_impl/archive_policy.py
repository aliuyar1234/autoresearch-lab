from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Iterable


@dataclasses.dataclass(frozen=True)
class RunRecord:
    experiment_id: str
    metric_value: float
    peak_vram_gb: float
    complexity_cost: int
    novelty_tags: tuple[str, ...]
    disposition: str
    lane: str


def pareto_front(runs: Iterable[RunRecord]) -> list[RunRecord]:
    items = list(runs)
    front: list[RunRecord] = []
    for a in items:
        dominated = False
        for b in items:
            if a.experiment_id == b.experiment_id:
                continue
            if (
                b.metric_value <= a.metric_value
                and b.peak_vram_gb <= a.peak_vram_gb
                and (b.metric_value < a.metric_value or b.peak_vram_gb < a.peak_vram_gb)
            ):
                dominated = True
                break
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda r: (r.metric_value, r.peak_vram_gb, r.complexity_cost))


def archive_buckets(
    runs: Iterable[RunRecord],
    *,
    champion_limit: int = 5,
    near_miss_limit: int = 8,
    novel_limit: int = 6,
) -> dict[str, list[RunRecord]]:
    items = list(runs)
    champions = sorted(
        [r for r in items if r.disposition == "promoted"],
        key=lambda r: (r.metric_value, r.complexity_cost),
    )[:champion_limit]

    pareto = pareto_front(items)

    near_misses = sorted(
        [r for r in items if r.disposition == "archived"],
        key=lambda r: (r.metric_value, r.complexity_cost),
    )[:near_miss_limit]

    by_novelty: dict[str, list[RunRecord]] = defaultdict(list)
    for run in items:
        for tag in run.novelty_tags:
            by_novelty[tag].append(run)

    novel_winners: list[RunRecord] = []
    for tag, tagged_runs in sorted(by_novelty.items()):
        best = min(tagged_runs, key=lambda r: (r.metric_value, r.complexity_cost))
        if best not in novel_winners:
            novel_winners.append(best)
    novel_winners = novel_winners[:novel_limit]

    return {
        "champions": champions,
        "pareto": pareto,
        "near_misses": near_misses,
        "novel_winners": novel_winners,
    }
