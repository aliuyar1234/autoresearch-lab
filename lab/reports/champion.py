from __future__ import annotations

import json
from typing import Any

from ..scheduler.compose import flatten_override_paths
from ..scoring import improvement


def build_champion_cards(campaign: dict[str, Any], experiments: list[dict[str, Any]]) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    promoted = [
        row
        for row in experiments
        if str(row.get("status")) == "completed"
        and str(row.get("disposition")) == "promoted"
        and row.get("primary_metric_value") is not None
    ]
    promoted.sort(key=lambda row: (_timestamp_sort_key(row), str(row["experiment_id"])))

    cards: list[dict[str, Any]] = []
    prior_promoted: list[dict[str, Any]] = []
    for row in promoted:
        previous = _best_metric(prior_promoted, direction=direction)
        cards.append(_build_card(campaign, row, previous=previous, direction=direction))
        prior_promoted.append(row)

    if not cards:
        fallback = _best_metric(
            [row for row in experiments if str(row.get("status")) == "completed" and row.get("primary_metric_value") is not None],
            direction=direction,
        )
        if fallback is not None:
            cards.append(_build_card(campaign, fallback, previous=None, direction=direction, fallback=True))

    cards = list(reversed(cards[-5:]))
    return {
        "campaign_id": campaign["campaign_id"],
        "cards": cards,
    }


def render_champion_cards_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# Champion Cards: {payload['campaign_id']}", ""]
    if not payload["cards"]:
        lines.append("No champion or promoted runs are available yet.")
        lines.append("")
        return "\n".join(lines)
    for card in payload["cards"]:
        delta_text = "n/a" if card["delta_vs_previous_champion"] is None else f"{card['delta_vs_previous_champion']:.6f}"
        lines.extend(
            [
                f"## {card['experiment_id']}",
                "",
                f"- Proposal: {card['proposal_id']}",
                f"- Family / kind: {card['proposal_family']} / {card['proposal_kind']}",
                f"- Date: {card['date']}",
                f"- Primary metric: {card['primary_metric']:.6f}",
                f"- Delta vs previous champion: {delta_text}",
                f"- Config fingerprint: {card['config_fingerprint']}",
                f"- Why it was better: {card['why_it_was_better']}",
                f"- Artifact path: {card['artifact_path']}",
                "- Key changes:",
            ]
        )
        for change in card["key_changes"]:
            lines.append(f"  - {change}")
        lines.append("")
    return "\n".join(lines)


def _build_card(
    campaign: dict[str, Any],
    row: dict[str, Any],
    *,
    previous: dict[str, Any] | None,
    direction: str,
    fallback: bool = False,
) -> dict[str, Any]:
    proposal_payload = _proposal_payload(row)
    config_overrides = proposal_payload.get("config_overrides", {})
    changes = [f"{path}={value}" for path, value in flatten_override_paths(config_overrides)]
    if not changes:
        changes = ["baseline / no explicit overrides"]

    metric_value = float(row["primary_metric_value"])
    delta = None
    if previous is not None and previous.get("primary_metric_value") is not None:
        delta = round(improvement(direction, float(previous["primary_metric_value"]), metric_value), 6)
        why = f"Improved {campaign['primary_metric']['name']} by {delta:.6f} versus {previous['experiment_id']}."
    elif fallback:
        why = "Best available completed run so far; no promoted champion exists yet."
    else:
        why = "Established the first promoted champion for this campaign state."

    return {
        "campaign": campaign["campaign_id"],
        "experiment_id": str(row["experiment_id"]),
        "proposal_id": row.get("proposal_id"),
        "proposal_family": row.get("proposal_family") or proposal_payload.get("family"),
        "proposal_kind": row.get("proposal_kind") or proposal_payload.get("kind"),
        "date": row.get("ended_at") or row.get("started_at"),
        "primary_metric": metric_value,
        "delta_vs_previous_champion": delta,
        "config_fingerprint": proposal_payload.get("config_fingerprint") or "unknown",
        "key_changes": changes[:6],
        "why_it_was_better": why,
        "artifact_path": row.get("artifact_root"),
    }


def _best_metric(experiments: list[dict[str, Any]], *, direction: str) -> dict[str, Any] | None:
    if not experiments:
        return None
    reverse = direction == "max"
    return sorted(
        experiments,
        key=lambda row: (
            float(row["primary_metric_value"]),
            -int(row.get("complexity_cost") or 0) if reverse else int(row.get("complexity_cost") or 0),
            str(row["experiment_id"]),
        ),
        reverse=reverse,
    )[0]


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _timestamp_sort_key(row: dict[str, Any]) -> str:
    return str(row.get("ended_at") or row.get("started_at") or "")


__all__ = ["build_champion_cards", "render_champion_cards_markdown"]
