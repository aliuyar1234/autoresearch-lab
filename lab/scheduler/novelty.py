from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from reference_impl.scheduler_policy import novelty_tags


def novelty_counter(overrides_payloads: Iterable[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for overrides in overrides_payloads:
        counts.update(novelty_tags(overrides))
    return counts


__all__ = ["novelty_counter", "novelty_tags"]
