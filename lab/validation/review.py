from __future__ import annotations

import json
import statistics
import uuid
from pathlib import Path
from typing import Any

from ..ledger.db import connect
from ..ledger.queries import (
    get_experiment,
    get_proposal,
    list_campaign_experiments,
    list_validation_reviews,
    replace_campaign_archive_rows,
    set_experiment_review_state,
    set_proposal_status,
    upsert_validation_review,
)
from ..memory import ingest_validation_review_memory
from ..paths import LabPaths
from ..replay import clone_proposal_for_replay, read_json_payload
from ..runner import execute_experiment
from ..scheduler import archive_rows_from_snapshot, build_archive_snapshot, write_archive_snapshot
from ..scoring import best_baseline, improvement
from ..semantics import is_rankable_experiment, is_validated_promotion, normalize_validation_state
from ..utils import load_schema, utc_now_iso, validate_payload, write_json
from .contracts import NoiseProbeResult, REVIEW_MODE_TO_RUN_PURPOSE, REVIEW_MODE_TO_SPLIT, ReviewRunRecord, ValidationReviewResult


def run_validation_review(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    source_experiment_id: str,
    mode: str,
    target_command_template: list[str],
    time_budget_seconds: int,
    device_profile: str | None = None,
    backend: str | None = None,
    dry_run: bool = False,
    reuse_comparator_replays: bool = True,
    force_replay: bool = False,
) -> ValidationReviewResult:
    if mode not in REVIEW_MODE_TO_SPLIT:
        raise ValueError(f"unsupported validation mode: {mode}")

    with connect(paths.db_path) as connection:
        source = get_experiment(connection, source_experiment_id)
        if not source:
            raise FileNotFoundError(f"experiment not found: {source_experiment_id}")
        proposal_row = get_proposal(connection, str(source["proposal_id"])) if source.get("proposal_id") else None
        proposal_payload = _load_proposal_payload(source, proposal_row)
        if mode == "confirm":
            existing = _latest_review(connection, source_experiment_id, mode)
            if existing and not force_replay:
                return ValidationReviewResult(**existing)
        comparator = _select_comparator(connection, campaign=campaign, source=source)
        comparator_payload = _load_proposal_payload(comparator, get_proposal(connection, str(comparator["proposal_id"]))) if comparator else None

    review_id = f"rev_{mode}_{uuid.uuid4().hex[:10]}"
    eval_split = REVIEW_MODE_TO_SPLIT[mode]
    run_purpose = REVIEW_MODE_TO_RUN_PURPOSE[mode]
    seed_list = [int(seed) for seed in campaign["budgets"].get("replication_seeds", [int(source.get("seed") or 42)])]
    created_at = utc_now_iso()

    if dry_run:
        payload = ValidationReviewResult(
            review_id=review_id,
            source_experiment_id=source_experiment_id,
            campaign_id=str(campaign["campaign_id"]),
            review_type=mode,
            eval_split=eval_split,
            candidate_experiment_ids=[],
            comparator_experiment_ids=[],
            seed_list=seed_list,
            decision="pending",
            reason="dry run; no validation replays were executed",
            candidate_metric_median=None,
            comparator_metric_median=None,
            delta_median=None,
            review={
                "candidate_source_experiment_id": source_experiment_id,
                "comparator_source_experiment_id": comparator["experiment_id"] if comparator else None,
                "seed_list": seed_list,
            },
            created_at=created_at,
            updated_at=created_at,
        )
        return payload

    candidate_runs = _materialize_review_runs(
        paths=paths,
        campaign=campaign,
        source_experiment=source,
        source_proposal=proposal_payload,
        review_id=review_id,
        eval_split=eval_split,
        run_purpose=run_purpose,
        seed_list=seed_list,
        target_command_template=target_command_template,
        time_budget_seconds=time_budget_seconds,
        device_profile=device_profile,
        backend=backend,
        force_replay=force_replay,
        allow_reuse=True,
        replay_lane="confirm" if mode == "confirm" else str(source["lane"]),
    )
    comparator_runs: list[ReviewRunRecord] = []
    if comparator is not None and comparator_payload is not None:
        comparator_runs = _materialize_review_runs(
            paths=paths,
            campaign=campaign,
            source_experiment=comparator,
            source_proposal=comparator_payload,
            review_id=review_id,
            eval_split=eval_split,
            run_purpose=run_purpose,
            seed_list=seed_list,
            target_command_template=target_command_template,
            time_budget_seconds=time_budget_seconds,
            device_profile=device_profile,
            backend=backend,
            force_replay=force_replay,
            allow_reuse=reuse_comparator_replays,
            replay_lane="confirm" if mode == "confirm" else str(source["lane"]),
        )

    candidate_metrics = [run.metric_value for run in candidate_runs]
    comparator_metrics = [run.metric_value for run in comparator_runs]
    candidate_median = _median(candidate_metrics)
    comparator_median = _median(comparator_metrics)
    paired_seeds = sorted(set(run.seed for run in candidate_runs) & set(run.seed for run in comparator_runs))
    candidate_by_seed = {run.seed: run.metric_value for run in candidate_runs}
    comparator_by_seed = {run.seed: run.metric_value for run in comparator_runs}
    delta_values = [
        round(
            improvement(
                str(campaign["primary_metric"]["direction"]),
                float(comparator_by_seed[seed]),
                float(candidate_by_seed[seed]),
            ),
            6,
        )
        for seed in paired_seeds
    ]
    delta_median = _median(delta_values)
    decision, reason, source_disposition, source_validation_state = _decide_review(
        campaign=campaign,
        source=source,
        comparator=comparator,
        delta_median=delta_median,
        mode=mode,
    )
    updated_at = utc_now_iso()
    review_payload = {
        "review_id": review_id,
        "source_experiment_id": source_experiment_id,
        "campaign_id": str(campaign["campaign_id"]),
        "review_type": mode,
        "eval_split": eval_split,
        "candidate_experiment_ids": [run.experiment_id for run in candidate_runs],
        "comparator_experiment_ids": [run.experiment_id for run in comparator_runs],
        "seed_list": seed_list,
        "candidate_metric_median": candidate_median,
        "comparator_metric_median": comparator_median,
        "delta_median": delta_median,
        "decision": decision,
        "reason": reason,
        "review": {
            "candidate_source_experiment_id": source_experiment_id,
            "comparator_source_experiment_id": comparator["experiment_id"] if comparator else None,
            "candidate_runs": [run.to_dict() for run in candidate_runs],
            "comparator_runs": [run.to_dict() for run in comparator_runs],
            "delta_values": delta_values,
        },
        "created_at": created_at,
        "updated_at": updated_at,
    }
    validate_payload(review_payload, load_schema(paths.schemas_root / "validation_review.schema.json"))

    with connect(paths.db_path) as connection:
        upsert_validation_review(connection, review_payload)
        ingest_validation_review_memory(connection, paths=paths, campaign=campaign, review=review_payload)
        if mode == "confirm":
            set_experiment_review_state(
                connection,
                source_experiment_id,
                disposition=source_disposition,
                validation_state=source_validation_state,
                validation_review_id=review_id,
                updated_at=updated_at,
            )
            if source.get("proposal_id"):
                set_proposal_status(connection, str(source["proposal_id"]), source_disposition, updated_at=updated_at)
            experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
            snapshot = build_archive_snapshot(experiments)
            replace_campaign_archive_rows(
                connection,
                str(campaign["campaign_id"]),
                archive_rows_from_snapshot(str(campaign["campaign_id"]), snapshot, created_at=updated_at),
            )
            write_archive_snapshot(paths, str(campaign["campaign_id"]), snapshot)
        connection.commit()

    return ValidationReviewResult(**review_payload)


def run_noise_probe(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    lane: str,
    count: int,
    seed_start: int,
    target_command_template: list[str],
    time_budget_seconds: int,
    device_profile: str | None = None,
    backend: str | None = None,
) -> NoiseProbeResult:
    baseline_proposal = _build_noise_proposal(campaign, lane=lane)
    metric_values: list[float] = []
    for seed in range(seed_start, seed_start + count):
        result = execute_experiment(
            paths=paths,
            proposal=baseline_proposal,
            campaign=campaign,
            target_command_template=target_command_template,
            seed=seed,
            time_budget_seconds=time_budget_seconds,
            device_profile=device_profile,
            backend=backend,
            eval_split="search_val",
            run_purpose="noise_probe",
            score_result=False,
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        metric_values.append(float(summary["primary_metric_value"]))

    metric_median = _median(metric_values)
    metric_min = min(metric_values) if metric_values else None
    metric_max = max(metric_values) if metric_values else None
    metric_range = None if metric_min is None or metric_max is None else round(metric_max - metric_min, 6)
    root = paths.reports_root / "noise" / str(campaign["campaign_id"])
    root.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z").replace("T", "_")
    json_path = root / f"noise_{lane}_{stamp}.json"
    md_path = root / f"noise_{lane}_{stamp}.md"
    payload = NoiseProbeResult(
        campaign_id=str(campaign["campaign_id"]),
        lane=lane,
        count=count,
        metric_values=[round(value, 6) for value in metric_values],
        metric_median=metric_median,
        metric_min=metric_min,
        metric_max=metric_max,
        metric_range=metric_range,
        artifact_paths={"report_json": str(json_path), "report_md": str(md_path)},
    )
    write_json(json_path, payload.to_dict())
    md_path.write_text(_render_noise_markdown(payload), encoding="utf-8")
    return payload


def _materialize_review_runs(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    source_experiment: dict[str, Any],
    source_proposal: dict[str, Any],
    review_id: str,
    eval_split: str,
    run_purpose: str,
    seed_list: list[int],
    target_command_template: list[str],
    time_budget_seconds: int,
    device_profile: str | None,
    backend: str | None,
    force_replay: bool,
    allow_reuse: bool,
    replay_lane: str,
) -> list[ReviewRunRecord]:
    existing_runs = _existing_review_runs(
        paths=paths,
        source_experiment_id=str(source_experiment["experiment_id"]),
        eval_split=eval_split,
        run_purpose=run_purpose,
    )
    by_seed = {row.seed: row for row in existing_runs}
    runs: list[ReviewRunRecord] = []
    for seed in seed_list:
        if allow_reuse and not force_replay and seed in by_seed:
            runs.append(by_seed[seed])
            continue
        replay_proposal = clone_proposal_for_replay(source_proposal, source_experiment_id=str(source_experiment["experiment_id"]))
        replay_proposal["lane"] = replay_lane
        result = execute_experiment(
            paths=paths,
            proposal=replay_proposal,
            campaign=campaign,
            target_command_template=target_command_template,
            seed=seed,
            time_budget_seconds=time_budget_seconds,
            device_profile=device_profile,
            backend=backend,
            eval_split=eval_split,
            run_purpose=run_purpose,
            validation_review_id=review_id,
            replay_source_experiment_id=str(source_experiment["experiment_id"]),
            score_result=False,
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        runs.append(
            ReviewRunRecord(
                experiment_id=result.experiment_id,
                replay_source_experiment_id=str(source_experiment["experiment_id"]),
                seed=int(summary["seed"]),
                metric_value=float(summary["primary_metric_value"]),
                summary_path=str(result.summary_path),
            )
        )
    return runs


def _existing_review_runs(*, paths: LabPaths, source_experiment_id: str, eval_split: str, run_purpose: str) -> list[ReviewRunRecord]:
    with connect(paths.db_path) as connection:
        experiments = list_campaign_experiments(connection, campaign_id=str(get_experiment(connection, source_experiment_id)["campaign_id"]))
    rows = [
        row
        for row in experiments
        if str(row.get("replay_source_experiment_id") or "") == source_experiment_id
        and str(row.get("eval_split") or "search_val") == eval_split
        and str(row.get("run_purpose") or "search") == run_purpose
        and str(row.get("status")) == "completed"
        and row.get("primary_metric_value") is not None
    ]
    return [
        ReviewRunRecord(
            experiment_id=str(row["experiment_id"]),
            replay_source_experiment_id=source_experiment_id,
            seed=int(row["seed"]),
            metric_value=float(row["primary_metric_value"]),
            summary_path=str(row.get("summary_path") or ""),
        )
        for row in rows
    ]


def _latest_review(connection, source_experiment_id: str, mode: str) -> dict[str, Any] | None:
    for review in list_validation_reviews(connection, source_experiment_id=source_experiment_id, limit=10):
        if review["review_type"] == mode and review["decision"] != "pending":
            return review
    return None


def _select_comparator(connection, *, campaign: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
    direction = str(campaign["primary_metric"]["direction"])
    promoted = [
        row
        for row in experiments
        if str(row.get("experiment_id")) != str(source["experiment_id"]) and is_validated_promotion(row)
    ]
    champion = _best_by_metric(promoted, direction=direction)
    if champion is not None:
        return champion
    baselines = [
        row
        for row in experiments
        if str(row.get("experiment_id")) != str(source["experiment_id"])
        and is_rankable_experiment(row)
        and str(row.get("proposal_family") or "") == "baseline"
        and str(row.get("status")) == "completed"
        and row.get("primary_metric_value") is not None
    ]
    return _best_by_metric(baselines, direction=direction)


def _best_by_metric(rows: list[dict[str, Any]], *, direction: str) -> dict[str, Any] | None:
    baseline = best_baseline(rows, direction=direction)
    if baseline is None:
        return None
    for row in rows:
        if str(row["experiment_id"]) == baseline.experiment_id:
            return row
    return None


def _load_proposal_payload(experiment_row: dict[str, Any], proposal_row: dict[str, Any] | None) -> dict[str, Any]:
    if proposal_row and proposal_row.get("proposal_json"):
        return read_json_payload(str(proposal_row["proposal_json"]))
    proposal_path = Path(str(experiment_row["artifact_root"])) / "proposal.json"
    return json.loads(proposal_path.read_text(encoding="utf-8"))


def _decide_review(
    *,
    campaign: dict[str, Any],
    source: dict[str, Any],
    comparator: dict[str, Any] | None,
    delta_median: float | None,
    mode: str,
) -> tuple[str, str, str | None, str | None]:
    if delta_median is None:
        return "failed", "no comparable replay metrics were produced", "discarded" if mode == "confirm" else None, "failed" if mode == "confirm" else None
    threshold = float(campaign["promotion"]["champion_min_delta"])
    tie_threshold = float(campaign["primary_metric"]["tie_threshold"])
    comparator_complexity = int(comparator.get("complexity_cost") or 9999) if comparator else 9999
    source_complexity = int(source.get("complexity_cost") or 0)
    if delta_median >= threshold:
        if mode == "confirm":
            return "passed", f"median delta {delta_median:.6f} >= {threshold:.6f}", "promoted", "passed"
        return "passed", f"{mode} median delta {delta_median:.6f} >= {threshold:.6f}", None, None
    if abs(delta_median - threshold) <= tie_threshold and source_complexity < comparator_complexity and bool(
        campaign["promotion"].get("allow_complexity_tie_break", True)
    ):
        if mode == "confirm":
            return "passed", f"median delta {delta_median:.6f} reached tie-break window with lower complexity", "promoted", "passed"
        return "passed", f"{mode} median delta {delta_median:.6f} passed complexity tie-break", None, None
    if mode == "confirm":
        disposition = "archived" if delta_median > 0 else "discarded"
        return "failed", f"median delta {delta_median:.6f} did not clear {threshold:.6f}", disposition, "failed"
    return "failed", f"{mode} median delta {delta_median:.6f} did not clear {threshold:.6f}", None, None


def _build_noise_proposal(campaign: dict[str, Any], *, lane: str) -> dict[str, Any]:
    timestamp = utc_now_iso()
    return {
        "proposal_id": f"p_{campaign['campaign_id']}_noise_{lane}_{uuid.uuid4().hex[:8]}",
        "campaign_id": campaign["campaign_id"],
        "lane": lane,
        "family": "baseline",
        "kind": "structured",
        "status": "queued",
        "created_at": timestamp,
        "generator": "noise_probe",
        "parent_ids": [],
        "hypothesis": "Repeat the clean baseline to estimate campaign noise.",
        "rationale": "Noise probes should not alter scientific knobs; they exist only to measure spread.",
        "config_overrides": {},
        "complexity_cost": 0,
        "expected_direction": "neutral",
        "tags": ["baseline", "noise_probe"],
        "novelty_reason": None,
        "notes": "Generated by lab.cli noise",
        "guardrails": {},
    }


def _render_noise_markdown(result: NoiseProbeResult) -> str:
    lines = [
        f"# Noise Probe: {result.campaign_id}",
        "",
        f"- Lane: {result.lane}",
        f"- Count: {result.count}",
        f"- Metric median: {result.metric_median if result.metric_median is not None else 'n/a'}",
        f"- Metric min: {result.metric_min if result.metric_min is not None else 'n/a'}",
        f"- Metric max: {result.metric_max if result.metric_max is not None else 'n/a'}",
        f"- Metric range: {result.metric_range if result.metric_range is not None else 'n/a'}",
        "",
        "## Values",
        "",
    ]
    for value in result.metric_values:
        lines.append(f"- {value:.6f}")
    lines.append("")
    return "\n".join(lines)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 6)
