from __future__ import annotations

from collections import Counter
from typing import Sequence


def build_recommendations(
    *,
    recent_crash_classes: Sequence[str],
    repeated_helpful_tags: Sequence[str],
    repeated_harmful_tags: Sequence[str],
    near_miss_count: int,
    confirm_promotions: int,
) -> list[str]:
    notes: list[str] = []
    crash_counts = Counter(recent_crash_classes)

    for crash_class, count in crash_counts.most_common():
        if count >= 3:
            notes.append(
                f"Reliability first: {count} recent `{crash_class}` failures suggest suppressing similar proposals until fixed."
            )

    if repeated_helpful_tags:
        top = Counter(repeated_helpful_tags).most_common(2)
        for tag, count in top:
            notes.append(f"Exploit region: `{tag}` helped in {count} recent runs and deserves local neighborhood search.")

    if repeated_harmful_tags:
        top = Counter(repeated_harmful_tags).most_common(1)
        for tag, count in top:
            notes.append(f"Avoid or ablate: `{tag}` regressed repeatedly in {count} recent runs.")

    if near_miss_count >= 3:
        notes.append(
            "There are several near-misses; schedule targeted ablations and combinations before opening a new code-lane initiative."
        )

    if confirm_promotions == 0:
        notes.append(
            "Few candidates are reaching confirm; widen scout novelty slightly or relax exploit locality to avoid overfitting one region."
        )

    if not notes:
        notes.append("Continue structured exploit around the current champion and strongest near-miss.")
    return notes
