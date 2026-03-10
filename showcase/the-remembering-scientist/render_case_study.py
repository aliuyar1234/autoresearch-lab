from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _shared import add_common_command_arguments, default_output_root, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render reproducible figure inputs and a case-study draft.")
    add_common_command_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = default_output_root(args.output_root)
    compare_path = output_root / "compare.json"
    validations_path = output_root / "validations" / "validation_summary.json"
    figure_root = output_root / "figures"
    figure_root.mkdir(parents=True, exist_ok=True)

    compare_payload = _read_optional_json(compare_path)
    validations_payload = _read_optional_json(validations_path)

    hero_curve = _hero_curve(compare_payload)
    morning_report = _morning_report_comparison(compare_payload)
    retrieval_panels = _retrieval_panels(validations_payload)
    lineage_graph = _lineage_graph(validations_payload)
    audit_panel = _audit_panel(validations_payload)
    repeated_dead_end = _repeated_dead_end(compare_payload, validations_payload)

    write_json(figure_root / "hero_curve.json", hero_curve)
    write_json(figure_root / "morning_report_comparison.json", morning_report)
    write_json(figure_root / "retrieval_panels.json", retrieval_panels)
    write_json(figure_root / "lineage_graph.json", lineage_graph)
    write_json(figure_root / "audit_panel.json", audit_panel)
    write_json(figure_root / "repeated_dead_end.json", repeated_dead_end)

    case_study = _render_case_study(
        compare_payload=compare_payload,
        validations_payload=validations_payload,
        figure_root=figure_root,
        campaign_id=str(args.campaign),
    )
    draft_path = output_root / "CASE_STUDY_DRAFT.md"
    draft_path.write_text(case_study, encoding="utf-8")
    payload = {
        "ok": compare_payload is not None,
        "status": "ready" if compare_payload is not None else "data_missing",
        "campaign_id": args.campaign,
        "figure_paths": {
            "hero_curve": str(figure_root / "hero_curve.json"),
            "morning_report_comparison": str(figure_root / "morning_report_comparison.json"),
            "retrieval_panels": str(figure_root / "retrieval_panels.json"),
            "lineage_graph": str(figure_root / "lineage_graph.json"),
            "audit_panel": str(figure_root / "audit_panel.json"),
            "repeated_dead_end": str(figure_root / "repeated_dead_end.json"),
        },
        "draft_path": str(draft_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _hero_curve(compare_payload: dict[str, Any] | None) -> dict[str, Any]:
    if compare_payload is None:
        return {"status": "data_missing", "series": []}
    series = []
    for pair in compare_payload.get("pairs", []):
        for arm_name in ("remembering", "amnesiac"):
            series.append(
                {
                    "pair_id": pair["pair_id"],
                    "arm": arm_name,
                    "curve": pair["arms"][arm_name]["session"].get("run_curve", []),
                }
            )
    return {"status": "ready", "series": series}


def _morning_report_comparison(compare_payload: dict[str, Any] | None) -> dict[str, Any]:
    if compare_payload is None:
        return {"status": "data_missing", "pairs": []}
    pairs = []
    for pair in compare_payload.get("pairs", []):
        pair_payload = {"pair_id": pair["pair_id"], "arms": {}}
        for arm_name in ("remembering", "amnesiac"):
            report = pair["arms"][arm_name]["report"]
            current_best = report.get("current_best_candidate") or {}
            pair_payload["arms"][arm_name] = {
                "report_root": report.get("report_root"),
                "promoted_count": report.get("promoted_count"),
                "failed_count": report.get("failed_count"),
                "current_best_candidate": current_best.get("experiment_id"),
                "current_best_trust_label": current_best.get("trust_label"),
                "current_best_trust_reason": current_best.get("trust_reason"),
                "top_failures": report.get("top_failures", []),
                "memory_citation_coverage": report.get("memory_citation_coverage"),
                "repeated_dead_end_rate": report.get("repeated_dead_end_rate"),
                "validation_pass_rate": report.get("validation_pass_rate"),
                "recommendations": report.get("recommendations", []),
            }
        pairs.append(pair_payload)
    return {"status": "ready", "pairs": pairs}


def _retrieval_panels(validations_payload: dict[str, Any] | None) -> dict[str, Any]:
    if validations_payload is None:
        return {"status": "data_missing", "examples": []}
    return {
        "status": "ready",
        "examples": list(validations_payload.get("memory_citation_examples", [])),
    }


def _lineage_graph(validations_payload: dict[str, Any] | None) -> dict[str, Any]:
    if validations_payload is None:
        return {"status": "data_missing", "nodes": [], "edges": []}
    nodes = []
    edges = []
    for item in validations_payload.get("candidate_lineage_references", []):
        experiment_id = str(item["experiment_id"])
        proposal_id = str(item["proposal_id"])
        nodes.append({"id": experiment_id, "type": "experiment", "arm": item.get("arm"), "pair_id": item.get("pair_id")})
        nodes.append({"id": proposal_id, "type": "proposal"})
        edges.append({"source": proposal_id, "target": experiment_id, "kind": "executed_as"})
    return {"status": "ready", "nodes": nodes, "edges": edges}


def _audit_panel(validations_payload: dict[str, Any] | None) -> dict[str, Any]:
    if validations_payload is None:
        return {"status": "data_missing", "arms": {}}
    return {
        "status": "ready",
        "arms": validations_payload.get("final_audit_comparison", {}),
    }


def _repeated_dead_end(compare_payload: dict[str, Any] | None, validations_payload: dict[str, Any] | None) -> dict[str, Any]:
    if compare_payload is None:
        return {"status": "data_missing", "aggregate": {}}
    payload = {
        "status": "ready",
        "aggregate": compare_payload.get("aggregate", {}).get("mean_repeated_dead_end_rate_by_arm", {}),
        "pair_details": {},
    }
    for pair in compare_payload.get("pairs", []):
        payload["pair_details"][pair["pair_id"]] = {
            arm_name: pair["arms"][arm_name]["report"].get("repeated_dead_end_rate")
            for arm_name in ("remembering", "amnesiac")
        }
    if validations_payload is not None:
        payload["validation_summary"] = validations_payload.get("repeated_dead_end_metrics", {})
    return payload


def _render_case_study(
    *,
    compare_payload: dict[str, Any] | None,
    validations_payload: dict[str, Any] | None,
    figure_root: Path,
    campaign_id: str,
) -> str:
    if compare_payload is None:
        return "\n".join(
            [
                f"# The Remembering Scientist: {campaign_id}",
                "",
                "Status: data missing",
                "",
                "The official A/B compare artifacts have not been generated yet.",
            ]
        ) + "\n"
    lines = [
        f"# The Remembering Scientist: {campaign_id}",
        "",
        "## Figure Inputs",
        "",
        f"- Hero curve: `{figure_root / 'hero_curve.json'}`",
        f"- Morning report comparison: `{figure_root / 'morning_report_comparison.json'}`",
        f"- Retrieval panels: `{figure_root / 'retrieval_panels.json'}`",
        f"- Lineage graph: `{figure_root / 'lineage_graph.json'}`",
        f"- Audit panel: `{figure_root / 'audit_panel.json'}`",
        f"- Repeated dead-end: `{figure_root / 'repeated_dead_end.json'}`",
        "",
        "## A/B Summary",
        "",
    ]
    for pair in compare_payload.get("pairs", []):
        lines.append(f"- {pair['pair_id']}: raw winner = {pair.get('winner_by_best_raw_metric') or 'n/a'}")
        for arm_name in ("remembering", "amnesiac"):
            report = pair["arms"][arm_name]["report"]
            candidate = report.get("current_best_candidate") or {}
            if candidate:
                lines.append(
                    f"  - {arm_name}: best candidate `{candidate['experiment_id']}` trust={candidate.get('trust_label') or 'unknown'}"
                )
    lines.extend(["", "## Validation Summary", ""])
    if validations_payload is None:
        lines.append("- Validation artifacts are missing.")
    else:
        for arm_name, finalist in validations_payload.get("final_primary_comparison", {}).items():
            if finalist is None:
                lines.append(f"- {arm_name}: finalist missing")
            else:
                lines.append(
                    f"- {arm_name}: confirm review `{finalist['review_id']}` "
                    f"candidate_median={finalist.get('candidate_metric_median')}"
                )
        lines.extend(["", "## Memory Citations", ""])
        for item in validations_payload.get("memory_citation_examples", [])[:5]:
            lines.append(
                f"- {item['arm']} / {item['experiment_id']}: {item['evidence_count']} citations "
                f"({item.get('retrieval_event_id') or 'no retrieval event'})"
            )
        lines.extend(["", "## Exact Artifact Paths", ""])
        lines.append(f"- Confirm comparison: `{validations_payload.get('confirm_comparison_path')}`")
        lines.append(f"- Audit comparison: `{validations_payload.get('audit_comparison_path')}`")
        lines.append(f"- Locked replays: `{validations_payload.get('clean_replays_path')}`")
    return "\n".join(lines) + "\n"


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
