from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .ledger.db import apply_migrations, connect
from .ledger.queries import append_agent_session_event, list_campaign_experiments, list_campaign_proposals, upsert_agent_session, upsert_campaign, upsert_proposal
from .preflight import run_preflight
from .reports import generate_report_bundle
from .resume import resume_interrupted_state
from .runner import execute_experiment
from .scheduler import DEFAULT_LANE_MIX, load_reviewed_scheduler_policy, policy_summary, plan_structured_queue, write_scheduler_policy_suggestion
from .scoring import assess_experiment_trust
from .semantics import is_completed_metric_run, is_rankable_experiment
from .utils import load_schema, utc_now_iso, validate_payload, write_json


def run_night_session(
    *,
    paths,
    campaign: dict[str, Any],
    hours: float,
    max_runs: int | None,
    allow_confirm: bool,
    seed_policy: str,
    target_command_template: list[str],
    device_profile: str | None = None,
    backend: str | None = None,
    max_code_runs: int | None = None,
    max_structured_runs: int | None = None,
    self_review_every_runs: int = 3,
    stop_on_consecutive_failures: int | None = 3,
) -> dict[str, Any]:
    apply_migrations(paths.db_path, paths.sql_root)
    session_started_at = utc_now_iso()
    session_id = _session_id(str(campaign["campaign_id"]), session_started_at)
    session_root = paths.reports_root / "_sessions" / str(campaign["campaign_id"]) / session_id
    checkpoints_root = session_root / "checkpoints"
    session_root.mkdir(parents=True, exist_ok=True)
    checkpoints_root.mkdir(parents=True, exist_ok=True)

    policy = load_reviewed_scheduler_policy(paths, str(campaign["campaign_id"]))
    executed: list[dict[str, Any]] = []
    checkpoint_paths: list[str] = []
    session_notes: list[str] = []
    queue_refills = 0
    self_review_count = 0
    lane_switch_count = 0
    current_lane_signature: str | None = None
    last_lane: str | None = None
    consecutive_failures = 0
    status = "running"
    stop_reason: str | None = None
    retrospective_path: str | None = None
    report_payload: dict[str, Any] = {}
    draft_policy_path: str | None = None

    _persist_session(
        paths=paths,
        session_id=session_id,
        campaign=campaign,
        session_started_at=session_started_at,
        session_ended_at=None,
        status=status,
        hours=hours,
        max_runs=max_runs,
        max_structured_runs=max_structured_runs,
        max_code_runs=max_code_runs,
        allow_confirm=allow_confirm,
        seed_policy=seed_policy,
        backend=backend,
        device_profile=device_profile,
        queue_refills=queue_refills,
        executed=executed,
        self_review_count=self_review_count,
        lane_switch_count=lane_switch_count,
        last_lane=last_lane,
        stop_reason=stop_reason,
        session_notes=session_notes,
        checkpoint_paths=checkpoint_paths,
        report_json_path=None,
        retrospective_json_path=None,
        policy=policy,
        draft_policy_path=draft_policy_path,
    )
    _append_session_event(
        paths=paths,
        session_id=session_id,
        event_type="session_started",
        created_at=session_started_at,
        payload={
            "campaign_id": str(campaign["campaign_id"]),
            "hours_budget": hours,
            "max_runs_budget": max_runs,
            "max_structured_runs_budget": max_structured_runs,
            "max_code_runs_budget": max_code_runs,
            "allow_confirm": allow_confirm,
            "seed_policy": seed_policy,
            "active_scheduler_policy": policy_summary(policy),
        },
    )

    resume_connection = connect(paths.db_path)
    try:
        resume_payload = resume_interrupted_state(resume_connection, paths=paths, campaign_id=str(campaign["campaign_id"]))
        resume_connection.commit()
    finally:
        resume_connection.close()
    session_notes.extend(list(resume_payload.get("notes", [])))

    preflight = run_preflight(paths, campaign_id=str(campaign["campaign_id"]), benchmark_backends=False)
    if not preflight.ok:
        status = "preflight_failed"
        stop_reason = status
        ended_at = utc_now_iso()
        _persist_session(
            paths=paths,
            session_id=session_id,
            campaign=campaign,
            session_started_at=session_started_at,
            session_ended_at=ended_at,
            status=status,
            hours=hours,
            max_runs=max_runs,
            max_structured_runs=max_structured_runs,
            max_code_runs=max_code_runs,
            allow_confirm=allow_confirm,
            seed_policy=seed_policy,
            backend=backend,
            device_profile=device_profile,
            queue_refills=queue_refills,
            executed=executed,
            self_review_count=self_review_count,
            lane_switch_count=lane_switch_count,
            last_lane=last_lane,
            stop_reason=stop_reason,
            session_notes=session_notes,
            checkpoint_paths=checkpoint_paths,
            report_json_path=None,
            retrospective_json_path=None,
            policy=policy,
            draft_policy_path=draft_policy_path,
        )
        return {
            "ok": False,
            "campaign_id": campaign["campaign_id"],
            "session_id": session_id,
            "session_root": str(session_root),
            "session_manifest_path": str(session_root / "session_manifest.json"),
            "status": status,
            "continuation_hint": f"Run `arlab preflight --campaign {campaign['campaign_id']}` and fix the reported env/config issues before retrying night.",
            "preflight": preflight.to_dict(),
            "resume": resume_payload,
        }

    deadline = time.monotonic() + max(0.0, hours) * 3600.0
    interrupted = False
    try:
        while True:
            stop_reason = _stop_reason(
                executed=executed,
                hours=hours,
                deadline=deadline,
                max_runs=max_runs,
                max_structured_runs=max_structured_runs,
                max_code_runs=max_code_runs,
                stop_on_consecutive_failures=stop_on_consecutive_failures,
                consecutive_failures=consecutive_failures,
            )
            if stop_reason is not None:
                break

            proposal = _next_queued_proposal(
                paths,
                str(campaign["campaign_id"]),
                allow_confirm=allow_confirm,
                executed=executed,
                max_code_runs=max_code_runs,
                max_structured_runs=max_structured_runs,
            )
            if proposal is None and _structured_budget_open(executed, max_structured_runs):
                refill_count = _fill_queue(paths, campaign, allow_confirm=allow_confirm, scheduler_policy=policy)
                if refill_count > 0:
                    queue_refills += 1
                    _append_session_event(
                        paths=paths,
                        session_id=session_id,
                        event_type="queue_refill",
                        created_at=utc_now_iso(),
                        payload={"refill_count": refill_count, "queue_refills": queue_refills},
                    )
                    proposal = _next_queued_proposal(
                        paths,
                        str(campaign["campaign_id"]),
                        allow_confirm=allow_confirm,
                        executed=executed,
                        max_code_runs=max_code_runs,
                        max_structured_runs=max_structured_runs,
                    )
            if proposal is None:
                stop_reason = "no_eligible_queued_work"
                break

            proposal_kind = _proposal_kind(proposal)
            lane = str(proposal["lane"])
            lane_signature = f"{proposal_kind}:{lane}"
            if current_lane_signature is not None and current_lane_signature != lane_signature:
                lane_switch_count += 1
                _append_session_event(
                    paths=paths,
                    session_id=session_id,
                    event_type="lane_switch",
                    lane=lane,
                    proposal_id=str(proposal["proposal_id"]),
                    created_at=utc_now_iso(),
                    payload={"from": current_lane_signature, "to": lane_signature},
                )
            current_lane_signature = lane_signature
            last_lane = lane

            result = execute_experiment(
                paths=paths,
                proposal=proposal,
                campaign=campaign,
                target_command_template=target_command_template,
                seed=_seed_for_run(campaign, run_index=len(executed), seed_policy=seed_policy),
                time_budget_seconds=int(campaign["budgets"][f"{lane}_seconds"]),
                device_profile=device_profile,
                backend=backend,
            )
            record = {
                "experiment_id": result.experiment_id,
                "proposal_id": result.proposal_id,
                "status": result.status,
                "crash_class": result.crash_class,
                "lane": lane,
                "proposal_kind": proposal_kind,
                "run_purpose": proposal.get("run_purpose") or ("confirm" if lane == "confirm" else "search"),
            }
            executed.append(record)
            consecutive_failures = 0 if result.status == "completed" else consecutive_failures + 1
            _append_session_event(
                paths=paths,
                session_id=session_id,
                event_type="run_completed",
                lane=lane,
                proposal_id=str(proposal["proposal_id"]),
                experiment_id=str(result.experiment_id),
                created_at=utc_now_iso(),
                payload=record,
            )

            if self_review_every_runs > 0 and len(executed) % self_review_every_runs == 0:
                self_review_count += 1
                checkpoint_path = _write_self_review_checkpoint(
                    paths=paths,
                    campaign=campaign,
                    session_id=session_id,
                    review_index=self_review_count,
                    executed=executed,
                    checkpoints_root=checkpoints_root,
                )
                checkpoint_paths.append(str(checkpoint_path))
                _append_session_event(
                    paths=paths,
                    session_id=session_id,
                    event_type="self_review_checkpoint",
                    created_at=utc_now_iso(),
                    report_path=str(checkpoint_path),
                    payload={"checkpoint_index": self_review_count, "checkpoint_path": str(checkpoint_path)},
                )
                _persist_session(
                    paths=paths,
                    session_id=session_id,
                    campaign=campaign,
                    session_started_at=session_started_at,
                    session_ended_at=None,
                    status=status,
                    hours=hours,
                    max_runs=max_runs,
                    max_structured_runs=max_structured_runs,
                    max_code_runs=max_code_runs,
                    allow_confirm=allow_confirm,
                    seed_policy=seed_policy,
                    backend=backend,
                    device_profile=device_profile,
                    queue_refills=queue_refills,
                    executed=executed,
                    self_review_count=self_review_count,
                    lane_switch_count=lane_switch_count,
                    last_lane=last_lane,
                    stop_reason=None,
                    session_notes=session_notes,
                    checkpoint_paths=checkpoint_paths,
                    report_json_path=None,
                    retrospective_json_path=None,
                    policy=policy,
                    draft_policy_path=draft_policy_path,
                )
    except KeyboardInterrupt:
        interrupted = True
        session_notes.append("Session ended early after an operator interruption.")
        stop_reason = "operator_interruption"

    ended_at = utc_now_iso()
    status = "interrupted" if interrupted else ("idle" if not executed else "completed")
    stop_reason = stop_reason or ("operator_interruption" if interrupted else ("no_work_executed" if not executed else "session_complete"))
    session_summary = _session_summary(
        session_id=session_id,
        campaign_id=str(campaign["campaign_id"]),
        session_started_at=session_started_at,
        session_ended_at=ended_at,
        status=status,
        stop_reason=stop_reason,
        hours=hours,
        max_runs=max_runs,
        max_structured_runs=max_structured_runs,
        max_code_runs=max_code_runs,
        allow_confirm=allow_confirm,
        seed_policy=seed_policy,
        backend=backend,
        device_profile=device_profile,
        queue_refills=queue_refills,
        executed=executed,
        self_review_count=self_review_count,
        lane_switch_count=lane_switch_count,
        last_lane=last_lane,
        checkpoint_paths=checkpoint_paths,
        policy=policy,
        draft_policy_path=draft_policy_path,
    )
    report_payload = _generate_final_report(
        paths,
        campaign=campaign,
        report_date=session_started_at[:10],
        started_at=session_started_at,
        ended_at=ended_at,
        session_notes=session_notes,
        session_summary=session_summary,
    )
    draft_policy_path = _write_scheduler_policy_suggestion_for_session(
        paths=paths,
        campaign_id=str(campaign["campaign_id"]),
        report_payload=report_payload,
    )
    session_summary["draft_scheduler_policy_path"] = draft_policy_path
    retrospective_path = str(_write_session_retrospective(session_root=session_root, report_payload=report_payload, session_summary=session_summary))
    _persist_session(
        paths=paths,
        session_id=session_id,
        campaign=campaign,
        session_started_at=session_started_at,
        session_ended_at=ended_at,
        status=status,
        hours=hours,
        max_runs=max_runs,
        max_structured_runs=max_structured_runs,
        max_code_runs=max_code_runs,
        allow_confirm=allow_confirm,
        seed_policy=seed_policy,
        backend=backend,
        device_profile=device_profile,
        queue_refills=queue_refills,
        executed=executed,
        self_review_count=self_review_count,
        lane_switch_count=lane_switch_count,
        last_lane=last_lane,
        stop_reason=stop_reason,
        session_notes=session_notes,
        checkpoint_paths=checkpoint_paths,
        report_json_path=report_payload.get("artifact_paths", {}).get("report_json"),
        retrospective_json_path=retrospective_path,
        policy=policy,
        draft_policy_path=draft_policy_path,
    )
    _append_session_event(
        paths=paths,
        session_id=session_id,
        event_type="session_completed",
        created_at=ended_at,
        report_path=report_payload.get("artifact_paths", {}).get("report_json"),
        payload={"status": status, "stop_reason": stop_reason, "retrospective_json_path": retrospective_path, "draft_policy_path": draft_policy_path},
    )
    return {
        "ok": bool(report_payload["ok"]),
        "campaign_id": campaign["campaign_id"],
        "session_id": session_id,
        "session_root": str(session_root),
        "session_manifest_path": str(session_root / "session_manifest.json"),
        "retrospective_json_path": retrospective_path,
        "status": status,
        "run_count": len(executed),
        "queue_refills": queue_refills,
        "executed": executed,
        "resume": resume_payload,
        "report": report_payload,
        "session_started_at": session_started_at,
        "session_ended_at": ended_at,
        "checkpoint_count": len(checkpoint_paths),
        "draft_scheduler_policy_path": draft_policy_path,
        "continuation_hint": _continuation_hint(campaign_id=str(campaign["campaign_id"]), status=status, resume_payload=resume_payload, run_count=len(executed)),
        "session": session_summary,
    }


def _fill_queue(paths, campaign: dict[str, Any], *, allow_confirm: bool, scheduler_policy: dict[str, Any] | None = None) -> int:
    connection = connect(paths.db_path)
    try:
        timestamp = utc_now_iso()
        upsert_campaign(connection, campaign, timestamp=timestamp)
        planned = plan_structured_queue(
            connection,
            paths=paths,
            campaign=campaign,
            count=5,
            lane_mix=_night_lane_mix(allow_confirm),
            scheduler_policy=scheduler_policy,
            persist=False,
        )
        for proposal in planned:
            validate_payload(proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
            upsert_proposal(connection, proposal, updated_at=proposal["created_at"])
        connection.commit()
        return len(planned)
    finally:
        connection.close()


def _next_queued_proposal(
    paths,
    campaign_id: str,
    *,
    allow_confirm: bool,
    executed: list[dict[str, Any]],
    max_code_runs: int | None,
    max_structured_runs: int | None,
) -> dict[str, Any] | None:
    connection = connect(paths.db_path)
    try:
        queued = list_campaign_proposals(connection, campaign_id, statuses=["queued"])
    finally:
        connection.close()
    code_count = sum(1 for row in executed if str(row.get("proposal_kind")) == "code_patch")
    structured_count = sum(1 for row in executed if str(row.get("proposal_kind")) != "code_patch")
    for row in queued:
        if not allow_confirm and str(row.get("lane")) == "confirm":
            continue
        payload = json.loads(row["proposal_json"])
        if not isinstance(payload, dict):
            continue
        kind = _proposal_kind(payload)
        if kind == "code_patch" and max_code_runs is not None and code_count >= max_code_runs:
            continue
        if kind != "code_patch" and max_structured_runs is not None and structured_count >= max_structured_runs:
            continue
        return payload
    return None


def _seed_for_run(campaign: dict[str, Any], *, run_index: int, seed_policy: str) -> int:
    seeds = [int(seed) for seed in campaign["budgets"].get("replication_seeds", [42])]
    if not seeds:
        return 42
    return seeds[run_index % len(seeds)] if seed_policy == "mixed" else seeds[0]


def _night_lane_mix(allow_confirm: bool) -> tuple[tuple[str, int], ...]:
    if allow_confirm:
        return DEFAULT_LANE_MIX
    return tuple((lane, weight) for lane, weight in DEFAULT_LANE_MIX if lane != "confirm")


def _generate_final_report(
    paths,
    *,
    campaign: dict[str, Any],
    report_date: str,
    started_at: str,
    ended_at: str,
    session_notes: list[str] | None = None,
    session_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    connection = connect(paths.db_path)
    try:
        experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
        payload = generate_report_bundle(
            connection,
            paths=paths,
            campaign=campaign,
            experiments=experiments,
            report_date=report_date,
            started_at=started_at,
            ended_at=ended_at,
            session_notes=session_notes,
            session_summary=session_summary,
        )
        connection.commit()
        return payload
    finally:
        connection.close()


def _persist_session(
    *,
    paths,
    session_id: str,
    campaign: dict[str, Any],
    session_started_at: str,
    session_ended_at: str | None,
    status: str,
    hours: float,
    max_runs: int | None,
    max_structured_runs: int | None,
    max_code_runs: int | None,
    allow_confirm: bool,
    seed_policy: str,
    backend: str | None,
    device_profile: str | None,
    queue_refills: int,
    executed: list[dict[str, Any]],
    self_review_count: int,
    lane_switch_count: int,
    last_lane: str | None,
    stop_reason: str | None,
    session_notes: list[str],
    checkpoint_paths: list[str],
    report_json_path: str | None,
    retrospective_json_path: str | None,
    policy: dict[str, Any] | None,
    draft_policy_path: str | None,
) -> None:
    summary = _session_summary(
        session_id=session_id,
        campaign_id=str(campaign["campaign_id"]),
        session_started_at=session_started_at,
        session_ended_at=session_ended_at,
        status=status,
        stop_reason=stop_reason,
        hours=hours,
        max_runs=max_runs,
        max_structured_runs=max_structured_runs,
        max_code_runs=max_code_runs,
        allow_confirm=allow_confirm,
        seed_policy=seed_policy,
        backend=backend,
        device_profile=device_profile,
        queue_refills=queue_refills,
        executed=executed,
        self_review_count=self_review_count,
        lane_switch_count=lane_switch_count,
        last_lane=last_lane,
        checkpoint_paths=checkpoint_paths,
        policy=policy,
        draft_policy_path=draft_policy_path,
    )
    manifest_path = paths.reports_root / "_sessions" / str(campaign["campaign_id"]) / session_id / "session_manifest.json"
    write_json(
        manifest_path,
        {
            "session": summary,
            "session_notes": list(session_notes),
            "executed": list(executed),
            "checkpoint_paths": list(checkpoint_paths),
            "report_json_path": report_json_path,
            "retrospective_json_path": retrospective_json_path,
        },
    )
    connection = connect(paths.db_path)
    try:
        upsert_campaign(connection, campaign, timestamp=session_started_at)
        upsert_agent_session(
            connection,
            {
                "session_id": session_id,
                "campaign_id": str(campaign["campaign_id"]),
                "status": status,
                "operator_mode": "agent",
                "started_at": session_started_at,
                "ended_at": session_ended_at,
                "hours_budget": hours,
                "max_runs_budget": max_runs,
                "max_structured_runs_budget": max_structured_runs,
                "max_code_runs_budget": max_code_runs,
                "allow_confirm": allow_confirm,
                "seed_policy": seed_policy,
                "backend": backend,
                "device_profile": device_profile,
                "queue_refills": queue_refills,
                "run_count": summary["run_count"],
                "structured_run_count": summary["structured_run_count"],
                "code_run_count": summary["code_run_count"],
                "confirm_run_count": summary["confirm_run_count"],
                "validation_review_count": summary["validation_review_count"],
                "report_checkpoint_count": summary["report_checkpoint_count"],
                "self_review_count": summary["self_review_count"],
                "lane_switch_count": summary["lane_switch_count"],
                "last_lane": last_lane,
                "stop_reason": stop_reason,
                "session_manifest_path": str(manifest_path),
                "retrospective_json_path": retrospective_json_path,
                "report_json_path": report_json_path,
                "session_summary": summary,
                "created_at": session_started_at,
                "updated_at": session_ended_at or utc_now_iso(),
            },
        )
        connection.commit()
    finally:
        connection.close()


def _append_session_event(
    *,
    paths,
    session_id: str,
    event_type: str,
    created_at: str,
    lane: str | None = None,
    proposal_id: str | None = None,
    experiment_id: str | None = None,
    report_path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    connection = connect(paths.db_path)
    try:
        append_agent_session_event(
            connection,
            session_id=session_id,
            event_type=event_type,
            lane=lane,
            proposal_id=proposal_id,
            experiment_id=experiment_id,
            report_path=report_path,
            payload=payload,
            created_at=created_at,
        )
        connection.commit()
    finally:
        connection.close()


def _session_summary(
    *,
    session_id: str,
    campaign_id: str,
    session_started_at: str,
    session_ended_at: str | None,
    status: str,
    stop_reason: str | None,
    hours: float,
    max_runs: int | None,
    max_structured_runs: int | None,
    max_code_runs: int | None,
    allow_confirm: bool,
    seed_policy: str,
    backend: str | None,
    device_profile: str | None,
    queue_refills: int,
    executed: list[dict[str, Any]],
    self_review_count: int,
    lane_switch_count: int,
    last_lane: str | None,
    checkpoint_paths: list[str],
    policy: dict[str, Any] | None,
    draft_policy_path: str | None,
) -> dict[str, Any]:
    structured_runs = [row for row in executed if str(row.get("proposal_kind")) != "code_patch"]
    code_runs = [row for row in executed if str(row.get("proposal_kind")) == "code_patch"]
    return {
        "session_id": session_id,
        "campaign_id": campaign_id,
        "status": status,
        "operator_mode": "agent",
        "started_at": session_started_at,
        "ended_at": session_ended_at,
        "stop_reason": stop_reason,
        "hours_budget": hours,
        "max_runs_budget": max_runs,
        "max_structured_runs_budget": max_structured_runs,
        "max_code_runs_budget": max_code_runs,
        "allow_confirm": allow_confirm,
        "seed_policy": seed_policy,
        "backend": backend,
        "device_profile": device_profile,
        "run_count": len(executed),
        "structured_run_count": len(structured_runs),
        "code_run_count": len(code_runs),
        "confirm_run_count": sum(1 for row in executed if str(row.get("lane")) == "confirm"),
        "validation_review_count": 0,
        "queue_refills": queue_refills,
        "self_review_count": self_review_count,
        "report_checkpoint_count": len(checkpoint_paths),
        "lane_switch_count": lane_switch_count,
        "last_lane": last_lane,
        "checkpoint_paths": list(checkpoint_paths),
        "recent_runs": list(executed[-5:]),
        "active_scheduler_policy": policy_summary(policy),
        "draft_scheduler_policy_path": draft_policy_path,
    }


def _write_self_review_checkpoint(
    *,
    paths,
    campaign: dict[str, Any],
    session_id: str,
    review_index: int,
    executed: list[dict[str, Any]],
    checkpoints_root: Path,
) -> Path:
    connection = connect(paths.db_path)
    try:
        experiments = list_campaign_experiments(connection, str(campaign["campaign_id"]))
    finally:
        connection.close()
    path = checkpoints_root / f"checkpoint_{review_index:03d}.json"
    write_json(
        path,
        _checkpoint_payload(
            campaign=campaign,
            session_id=session_id,
            review_index=review_index,
            executed=executed,
            experiments=experiments,
        ),
    )
    return path


def _checkpoint_payload(
    *,
    campaign: dict[str, Any],
    session_id: str,
    review_index: int,
    executed: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    direction = str(campaign["primary_metric"]["direction"])
    completed = [row for row in experiments if is_completed_metric_run(row) and is_rankable_experiment(row)]
    failure_counts = Counter(str(row.get("crash_class") or "unknown") for row in experiments if str(row.get("status")) != "completed")
    return {
        "session_id": session_id,
        "checkpoint_index": review_index,
        "created_at": utc_now_iso(),
        "run_count": len(executed),
        "structured_run_count": sum(1 for row in executed if str(row.get("proposal_kind")) != "code_patch"),
        "code_run_count": sum(1 for row in executed if str(row.get("proposal_kind")) == "code_patch"),
        "strongest_surviving_candidates": [_checkpoint_row(row, campaign) for row in _top_metric_rows(completed, direction=direction, limit=3)],
        "strongest_rejected_candidates": [_checkpoint_row(row, campaign) for row in _top_metric_rows(_rejected_rows(completed), direction=direction, limit=3)],
        "top_failures": [{"crash_class": crash_class, "count": count} for crash_class, count in failure_counts.most_common(3)],
    }


def _checkpoint_row(row: dict[str, Any], campaign: dict[str, Any]) -> dict[str, Any]:
    trust = assess_experiment_trust(experiment=row, direction=str(campaign["primary_metric"]["direction"]))
    proposal_payload = _proposal_payload(row)
    return {
        "experiment_id": str(row["experiment_id"]),
        "proposal_id": row.get("proposal_id"),
        "proposal_family": row.get("proposal_family") or proposal_payload.get("family"),
        "proposal_kind": row.get("proposal_kind") or proposal_payload.get("kind"),
        "lane": row.get("lane"),
        "primary_metric_value": float(row["primary_metric_value"]) if row.get("primary_metric_value") is not None else None,
        "disposition": row.get("disposition"),
        "validation_state": row.get("validation_state"),
        "trust_label": trust.label,
        "trust_reason": trust.reason,
    }


def _write_session_retrospective(*, session_root: Path, report_payload: dict[str, Any], session_summary: dict[str, Any]) -> Path:
    path = session_root / "retrospective.json"
    write_json(
        path,
        {
            "session": session_summary,
            "current_best_candidate": report_payload.get("current_best_candidate"),
            "strongest_surviving_candidates": report_payload.get("top_outcomes", {}).get("best_confirmed_candidates", []),
            "strongest_rejected_candidates": report_payload.get("top_outcomes", {}).get("strongest_rejected_candidates", []),
            "top_failures": report_payload.get("decision_summary", {}).get("top_failures", []),
            "next_actions": report_payload.get("decision_summary", {}).get("next_actions", []),
            "lane_comparison": report_payload.get("lane_comparison", {}),
            "memory_policy_summary": report_payload.get("memory_policy_summary", {}),
        },
    )
    return path


def _write_scheduler_policy_suggestion_for_session(*, paths, campaign_id: str, report_payload: dict[str, Any]) -> str | None:
    what_changed = list(report_payload.get("what_changed", []))
    if not what_changed:
        return None
    family_scores: dict[str, float] = {}
    for item in what_changed:
        family = str(item.get("family") or "")
        if not family:
            continue
        family_scores[family] = (
            float(item.get("promoted_count") or 0) * 2.0
            + float(item.get("run_count") or 0) * 0.1
            - float(item.get("failed_count") or 0) * 0.75
        )
    preferred = [family for family, score in sorted(family_scores.items(), key=lambda item: (-item[1], item[0]))[:2] if score > 0]
    blocked = [family for family, score in sorted(family_scores.items(), key=lambda item: (item[1], item[0]))[:1] if score < 0]
    if not preferred and not blocked:
        return None
    path = write_scheduler_policy_suggestion(
        paths=paths,
        campaign_id=campaign_id,
        family_weights={family: max(0.5, min(3.0, 1.0 + score)) for family, score in family_scores.items()},
        preferred_families=preferred,
        blocked_families=blocked,
        rationale="Auto-generated from the latest autonomous session retrospective. Review before promotion.",
        notes=list(report_payload.get("recommendations", [])) if isinstance(report_payload.get("recommendations"), list) else [],
        review_state="draft",
    )
    return str(path)


def _stop_reason(
    *,
    executed: list[dict[str, Any]],
    hours: float,
    deadline: float,
    max_runs: int | None,
    max_structured_runs: int | None,
    max_code_runs: int | None,
    stop_on_consecutive_failures: int | None,
    consecutive_failures: int,
) -> str | None:
    if max_runs is not None and len(executed) >= max_runs:
        return "max_runs_budget_reached"
    if hours > 0 and time.monotonic() >= deadline:
        return "time_budget_exhausted"
    if stop_on_consecutive_failures is not None and stop_on_consecutive_failures > 0 and consecutive_failures >= stop_on_consecutive_failures:
        return "consecutive_failures_threshold"
    structured_count = sum(1 for row in executed if str(row.get("proposal_kind")) != "code_patch")
    code_count = sum(1 for row in executed if str(row.get("proposal_kind")) == "code_patch")
    if max_structured_runs is not None and max_code_runs is not None and structured_count >= max_structured_runs and code_count >= max_code_runs:
        return "all_lane_budgets_exhausted"
    return None


def _proposal_kind(proposal: dict[str, Any]) -> str:
    return "code_patch" if str(proposal.get("kind") or "") == "code_patch" else "structured"


def _structured_budget_open(executed: list[dict[str, Any]], max_structured_runs: int | None) -> bool:
    if max_structured_runs is None:
        return True
    return sum(1 for row in executed if str(row.get("proposal_kind")) != "code_patch") < max_structured_runs


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rejected_rows(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in experiments
        if str(row.get("validation_state") or "") == "failed"
        or str(row.get("disposition") or "") in {"archived", "discarded"}
    ]


def _top_metric_rows(experiments: list[dict[str, Any]], *, direction: str, limit: int) -> list[dict[str, Any]]:
    reverse = direction == "max"
    return sorted(
        experiments,
        key=lambda row: (
            float(row["primary_metric_value"]),
            int(row.get("complexity_cost") or 0),
            str(row.get("experiment_id") or ""),
        ),
        reverse=reverse,
    )[:limit]


def _session_id(campaign_id: str, started_at: str) -> str:
    return f"session_{campaign_id}_{_safe_stamp(started_at)}"


def _safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z").replace("T", "_")


def _continuation_hint(*, campaign_id: str, status: str, resume_payload: dict[str, Any], run_count: int) -> str:
    if status == "interrupted":
        return f"Rerun `arlab night --campaign {campaign_id} ...`; the session auto-resumes proposals left in `running` state first."
    if status == "idle":
        if resume_payload.get("status") == "recovered":
            return f"Rerun `arlab night --campaign {campaign_id} ...` to execute the requeued proposals recovered at session start."
        return f"No queued work remained for {campaign_id}; generate new proposals or rerun night later."
    if resume_payload.get("status") == "recovered" and run_count > 0:
        return f"Recovered interrupted work first and finished the session; rerun `night` later to continue exploring {campaign_id}."
    return f"Night session completed cleanly for {campaign_id}; inspect the report before scheduling more runs."


__all__ = ["run_night_session"]
