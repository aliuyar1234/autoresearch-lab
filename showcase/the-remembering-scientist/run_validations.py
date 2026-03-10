from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _shared import (
    add_common_command_arguments,
    build_replay_payload,
    candidate_record,
    default_output_root,
    dedupe_candidates,
    load_showcase_campaign,
    parse_target_command,
    workspace_paths,
    write_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run confirm, audit, and replay steps for showcase arms.")
    add_common_command_arguments(parser)
    parser.add_argument("--top-per-arm", type=int, default=2)
    parser.add_argument("--time-budget-seconds", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = default_output_root(args.output_root)
    compare_path = output_root / "compare.json"
    if not compare_path.exists():
        payload = {"ok": False, "status": "data_missing", "reason": f"missing compare.json under {output_root}"}
        write_json(output_root / "validations" / "validation_summary.json", payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))
    target_command = parse_target_command(
        target_command=args.target_command,
        target_command_json=args.target_command_json,
    )
    validations_root = output_root / "validations"
    validations_root.mkdir(parents=True, exist_ok=True)

    from lab.ledger.db import connect
    from lab.ledger.queries import list_campaign_experiments
    from lab.validation import run_validation_review

    candidate_pool: dict[str, list[dict[str, Any]]] = {"remembering": [], "amnesiac": []}
    arm_paths_map: dict[tuple[str, str], Any] = {}
    campaign_direction = "min"
    for pair in compare_payload.get("pairs", []):
        for arm_name in ("remembering", "amnesiac"):
            arm = pair["arms"][arm_name]
            paths = workspace_paths(Path(str(arm["workspace_root"])))
            arm_paths_map[(pair["pair_id"], arm_name)] = paths
            campaign = load_showcase_campaign(paths, str(args.campaign))
             # base campaign direction drives all candidate comparisons.
            campaign_direction = str(campaign["primary_metric"]["direction"])
            executed_ids = {str(item["experiment_id"]) for item in arm["session"]["executed"]}
            with connect(paths.db_path) as connection:
                rows = [
                    row
                    for row in list_campaign_experiments(connection, str(args.campaign))
                    if str(row["experiment_id"]) in executed_ids
                    and str(row.get("status")) == "completed"
                    and row.get("primary_metric_value") is not None
                ]
            for row in rows:
                payload = candidate_record(campaign=campaign, row=row)
                payload["pair_id"] = str(pair["pair_id"])
                payload["arm"] = arm_name
                candidate_pool[arm_name].append(payload)

    deduped_pool = {
        arm_name: dedupe_candidates(
            list(candidates),
            direction=campaign_direction,
            limit=int(args.top_per_arm),
        )
        for arm_name, candidates in candidate_pool.items()
    }
    write_json(validations_root / "candidate_pool.json", deduped_pool)

    confirm_summary: dict[str, Any] = {"arms": {}}
    finalists: dict[str, dict[str, Any] | None] = {"remembering": None, "amnesiac": None}
    for arm_name, candidates in deduped_pool.items():
        reviews: list[dict[str, Any]] = []
        for candidate in candidates:
            paths = arm_paths_map[(str(candidate["pair_id"]), arm_name)]
            campaign = load_showcase_campaign(paths, str(args.campaign))
            review = run_validation_review(
                paths=paths,
                campaign=campaign,
                source_experiment_id=str(candidate["experiment_id"]),
                mode="confirm",
                target_command_template=target_command,
                time_budget_seconds=int(args.time_budget_seconds or campaign["budgets"]["confirm_seconds"]),
                device_profile=getattr(args, "device_profile", None),
                backend=getattr(args, "backend", None),
            )
            review_payload = review.to_dict()
            review_payload["pair_id"] = str(candidate["pair_id"])
            review_payload["arm"] = arm_name
            review_payload["source_candidate"] = candidate
            reviews.append(review_payload)
        finalists[arm_name] = _select_finalist(reviews, direction=campaign_direction)
        confirm_summary["arms"][arm_name] = {"reviews": reviews, "finalist": finalists[arm_name]}
    write_json(validations_root / "confirm_comparison.json", confirm_summary)

    audit_summary: dict[str, Any] = {"arms": {}}
    for arm_name, finalist in finalists.items():
        if finalist is None:
            audit_summary["arms"][arm_name] = {"status": "data_missing"}
            continue
        pair_id = str(finalist["pair_id"])
        paths = arm_paths_map[(pair_id, arm_name)]
        campaign = load_showcase_campaign(paths, str(args.campaign))
        review = run_validation_review(
            paths=paths,
            campaign=campaign,
            source_experiment_id=str(finalist["source_experiment_id"]),
            mode="audit",
            target_command_template=target_command,
            time_budget_seconds=int(args.time_budget_seconds or campaign["budgets"]["confirm_seconds"]),
            device_profile=getattr(args, "device_profile", None),
            backend=getattr(args, "backend", None),
        )
        audit_summary["arms"][arm_name] = review.to_dict()
    write_json(validations_root / "audit_comparison.json", audit_summary)

    baseline_source = _select_baseline_source(candidate_pool, direction=campaign_direction)
    clean_replays: dict[str, Any] = {}
    if baseline_source is None:
        clean_replays["baseline"] = {"status": "data_missing"}
    else:
        pair_id, arm_name, experiment_id = baseline_source
        paths = arm_paths_map[(pair_id, arm_name)]
        campaign = load_showcase_campaign(paths, str(args.campaign))
        clean_replays["baseline"] = build_replay_payload(
            paths=paths,
            campaign=campaign,
            source_experiment_id=experiment_id,
            target_command_template=target_command,
            device_profile=getattr(args, "device_profile", None),
            backend=getattr(args, "backend", None),
            eval_split="locked_val",
            run_purpose="replay",
            time_budget_seconds=int(args.time_budget_seconds or campaign["budgets"]["confirm_seconds"]),
        )
    for arm_name, finalist in finalists.items():
        if finalist is None:
            clean_replays[arm_name] = {"status": "data_missing"}
            continue
        pair_id = str(finalist["pair_id"])
        paths = arm_paths_map[(pair_id, arm_name)]
        campaign = load_showcase_campaign(paths, str(args.campaign))
        clean_replays[arm_name] = build_replay_payload(
            paths=paths,
            campaign=campaign,
            source_experiment_id=str(finalist["source_experiment_id"]),
            target_command_template=target_command,
            device_profile=getattr(args, "device_profile", None),
            backend=getattr(args, "backend", None),
            eval_split="locked_val",
            run_purpose="replay",
            time_budget_seconds=int(args.time_budget_seconds or campaign["budgets"]["confirm_seconds"]),
        )
    write_json(validations_root / "clean_replays.json", clean_replays)

    memory_citation_examples = _memory_citation_examples(candidate_pool)
    repeated_dead_end_metrics = _repeated_dead_end_metrics(compare_payload)
    candidate_lineage_references = _candidate_lineage_references(deduped_pool)
    validation_summary = {
        "ok": True,
        "campaign_id": args.campaign,
        "candidate_pool_path": str(validations_root / "candidate_pool.json"),
        "confirm_comparison_path": str(validations_root / "confirm_comparison.json"),
        "audit_comparison_path": str(validations_root / "audit_comparison.json"),
        "clean_replays_path": str(validations_root / "clean_replays.json"),
        "final_primary_comparison": {
            arm_name: finalists[arm_name]
            for arm_name in ("remembering", "amnesiac")
        },
        "final_audit_comparison": audit_summary["arms"],
        "memory_citation_examples": memory_citation_examples,
        "repeated_dead_end_metrics": repeated_dead_end_metrics,
        "candidate_lineage_references": candidate_lineage_references,
    }
    write_json(validations_root / "validation_summary.json", validation_summary)
    print(json.dumps(validation_summary, indent=2, sort_keys=True))
    return 0


def _select_finalist(reviews: list[dict[str, Any]], *, direction: str) -> dict[str, Any] | None:
    if not reviews:
        return None
    passed = [review for review in reviews if review.get("decision") == "passed" and review.get("candidate_metric_median") is not None]
    pool = passed or [review for review in reviews if review.get("candidate_metric_median") is not None]
    if not pool:
        return None
    return sorted(
        pool,
        key=lambda review: (float(review["candidate_metric_median"]), str(review["review_id"])),
        reverse=direction == "max",
    )[0]


def _select_baseline_source(candidate_pool: dict[str, list[dict[str, Any]]], *, direction: str) -> tuple[str, str, str] | None:
    baseline_candidates = []
    for arm_name, candidates in candidate_pool.items():
        for candidate in candidates:
            if str(candidate.get("proposal_family")) == "baseline":
                baseline_candidates.append((arm_name, candidate))
    if not baseline_candidates:
        return None
    arm_name, candidate = sorted(
        baseline_candidates,
        key=lambda item: (float(item[1]["primary_metric_value"]), str(item[1]["experiment_id"])),
        reverse=direction == "max",
    )[0]
    return (str(candidate["pair_id"]), arm_name, str(candidate["experiment_id"]))


def _memory_citation_examples(candidate_pool: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for arm_name, candidates in candidate_pool.items():
        for candidate in candidates:
            if candidate.get("evidence_count", 0) <= 0:
                continue
            examples.append(
                {
                    "arm": arm_name,
                    "experiment_id": candidate["experiment_id"],
                    "retrieval_event_id": candidate.get("retrieval_event_id"),
                    "evidence_count": candidate.get("evidence_count"),
                    "evidence_memory_ids": candidate.get("evidence_memory_ids", []),
                }
            )
    return examples[:6]


def _repeated_dead_end_metrics(compare_payload: dict[str, Any]) -> dict[str, Any]:
    per_arm: dict[str, list[float]] = {"remembering": [], "amnesiac": []}
    for pair in compare_payload.get("pairs", []):
        for arm_name in ("remembering", "amnesiac"):
            value = pair["arms"][arm_name]["report"].get("repeated_dead_end_rate")
            if value is not None:
                per_arm[arm_name].append(float(value))
    return {
        arm_name: round(sum(values) / len(values), 6) if values else None
        for arm_name, values in per_arm.items()
    }


def _candidate_lineage_references(candidate_pool: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    for arm_name, candidates in candidate_pool.items():
        for candidate in candidates:
            lineage.append(
                {
                    "pair_id": candidate["pair_id"],
                    "arm": arm_name,
                    "experiment_id": candidate["experiment_id"],
                    "proposal_id": candidate["proposal_id"],
                    "parent_ids": candidate.get("parent_ids", []),
                    "evidence_memory_ids": candidate.get("evidence_memory_ids", []),
                    "retrieval_event_id": candidate.get("retrieval_event_id"),
                }
            )
    return lineage


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
