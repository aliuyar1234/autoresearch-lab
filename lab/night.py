from __future__ import annotations

import json
import time
from typing import Any

from .ledger.db import apply_migrations, connect
from .ledger.queries import list_campaign_experiments, list_campaign_proposals, upsert_campaign, upsert_proposal
from .preflight import run_preflight
from .resume import resume_interrupted_state
from .reports import generate_report_bundle
from .runner import execute_experiment
from .scheduler import DEFAULT_LANE_MIX, plan_structured_queue
from .utils import load_schema, utc_now_iso, validate_payload


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
) -> dict[str, Any]:
    apply_migrations(paths.db_path, paths.sql_root)
    resume_connection = connect(paths.db_path)
    try:
        resume_payload = resume_interrupted_state(
            resume_connection,
            paths=paths,
            campaign_id=str(campaign["campaign_id"]),
        )
        resume_connection.commit()
    finally:
        resume_connection.close()

    preflight = run_preflight(paths, campaign_id=str(campaign["campaign_id"]), benchmark_backends=False)
    if not preflight.ok:
        return {
            "ok": False,
            "campaign_id": campaign["campaign_id"],
            "status": "preflight_failed",
            "preflight": preflight.to_dict(),
            "resume": resume_payload,
        }

    session_started_at = utc_now_iso()
    deadline = time.monotonic() + max(0.0, hours) * 3600.0
    executed: list[dict[str, Any]] = []
    queue_refills = 0
    interrupted = False
    session_notes = list(resume_payload.get("notes", []))

    try:
        while True:
            if max_runs is not None and len(executed) >= max_runs:
                break
            if hours > 0 and time.monotonic() >= deadline:
                break

            proposal = _next_queued_proposal(paths, str(campaign["campaign_id"]), allow_confirm=allow_confirm)
            if proposal is None:
                refill_count = _fill_queue(paths, campaign, allow_confirm=allow_confirm)
                if refill_count == 0:
                    break
                queue_refills += 1
                proposal = _next_queued_proposal(paths, str(campaign["campaign_id"]), allow_confirm=allow_confirm)
                if proposal is None:
                    break

            lane = str(proposal["lane"])
            seed = _seed_for_run(campaign, run_index=len(executed), seed_policy=seed_policy)
            time_budget_seconds = int(campaign["budgets"][f"{lane}_seconds"])
            result = execute_experiment(
                paths=paths,
                proposal=proposal,
                campaign=campaign,
                target_command_template=target_command_template,
                seed=seed,
                time_budget_seconds=time_budget_seconds,
                device_profile=device_profile,
                backend=backend,
            )
            executed.append(
                {
                    "experiment_id": result.experiment_id,
                    "proposal_id": result.proposal_id,
                    "status": result.status,
                    "crash_class": result.crash_class,
                }
            )
    except KeyboardInterrupt:
        interrupted = True
        session_notes.append("Session ended early after an operator interruption.")

    report_payload = _generate_final_report(
        paths,
        campaign=campaign,
        report_date=session_started_at[:10],
        started_at=session_started_at,
        session_notes=session_notes,
    )
    return {
        "ok": bool(report_payload["ok"]),
        "campaign_id": campaign["campaign_id"],
        "status": "interrupted" if interrupted else "completed",
        "run_count": len(executed),
        "queue_refills": queue_refills,
        "executed": executed,
        "resume": resume_payload,
        "report": report_payload,
        "session_started_at": session_started_at,
        "session_ended_at": utc_now_iso(),
    }


def _fill_queue(paths, campaign: dict[str, Any], *, allow_confirm: bool) -> int:
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
            persist=False,
        )
        for proposal in planned:
            validate_payload(proposal, load_schema(paths.schemas_root / "proposal.schema.json"))
            upsert_proposal(connection, proposal, updated_at=proposal["created_at"])
        connection.commit()
        return len(planned)
    finally:
        connection.close()


def _next_queued_proposal(paths, campaign_id: str, *, allow_confirm: bool) -> dict[str, Any] | None:
    connection = connect(paths.db_path)
    try:
        queued = list_campaign_proposals(connection, campaign_id, statuses=["queued"])
    finally:
        connection.close()
    for row in queued:
        if not allow_confirm and str(row.get("lane")) == "confirm":
            continue
        payload = json.loads(row["proposal_json"])
        if isinstance(payload, dict):
            return payload
    return None


def _seed_for_run(campaign: dict[str, Any], *, run_index: int, seed_policy: str) -> int:
    seeds = [int(seed) for seed in campaign["budgets"].get("replication_seeds", [42])]
    if not seeds:
        return 42
    if seed_policy == "mixed":
        return seeds[run_index % len(seeds)]
    return seeds[0]


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
    session_notes: list[str] | None = None,
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
            ended_at=utc_now_iso(),
            session_notes=session_notes,
        )
        connection.commit()
        return payload
    finally:
        connection.close()


__all__ = ["run_night_session"]
