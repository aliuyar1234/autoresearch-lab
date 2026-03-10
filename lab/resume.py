from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import build_artifact_record, write_artifact_index
from .campaigns.load import load_campaign
from .ledger.queries import list_campaign_experiments, list_proposal_experiments, list_running_proposals, replace_artifacts, replace_campaign_archive_rows, set_proposal_status, upsert_experiment
from .scheduler import archive_rows_from_snapshot, build_archive_snapshot, write_archive_snapshot
from .utils import read_json, utc_now_iso, write_json

TERMINAL_EXPERIMENT_STATUSES = {"completed", "failed", "discarded", "promoted"}


def resume_interrupted_state(connection, *, paths, campaign_id: str | None = None) -> dict[str, Any]:
    running = list_running_proposals(connection, campaign_id=campaign_id)
    timestamp = utc_now_iso()
    touched_campaigns: set[str] = set()
    finalized: list[dict[str, str]] = []
    requeued: list[dict[str, str]] = []
    recovered_experiments: list[str] = []
    synthesized_experiments: list[str] = []

    for row in running:
        proposal = _proposal_payload(row)
        proposal_id = str(row["proposal_id"])
        proposal_campaign_id = str(row["campaign_id"])
        touched_campaigns.add(proposal_campaign_id)

        latest_terminal = _latest_terminal_experiment(connection, proposal_id)
        if latest_terminal is not None:
            status = _proposal_terminal_status(latest_terminal)
            set_proposal_status(connection, proposal_id, status, updated_at=timestamp)
            finalized.append(
                {
                    "proposal_id": proposal_id,
                    "status": status,
                    "experiment_id": str(latest_terminal["experiment_id"]),
                }
            )
            continue

        run_root = _latest_run_root_for_proposal(paths.runs_root, proposal_id)
        if run_root is None:
            set_proposal_status(connection, proposal_id, "queued", updated_at=timestamp)
            requeued.append(
                {
                    "proposal_id": proposal_id,
                    "reason": "no_artifacts",
                }
            )
            continue

        campaign = load_campaign(paths, proposal_campaign_id)
        recovered = _recover_or_interrupt_run(
            connection,
            paths=paths,
            run_root=run_root,
            proposal=proposal,
            campaign=campaign,
        )
        recovered_experiments.append(recovered["experiment_id"])
        if recovered["synthesized_summary"]:
            synthesized_experiments.append(recovered["experiment_id"])
            set_proposal_status(connection, proposal_id, "queued", updated_at=timestamp)
            requeued.append(
                {
                    "proposal_id": proposal_id,
                    "reason": "interrupted_run",
                    "experiment_id": recovered["experiment_id"],
                }
            )
        else:
            set_proposal_status(connection, proposal_id, recovered["proposal_status"], updated_at=timestamp)
            finalized.append(
                {
                    "proposal_id": proposal_id,
                    "status": recovered["proposal_status"],
                    "experiment_id": recovered["experiment_id"],
                }
            )

    for resumed_campaign_id in sorted(touched_campaigns):
        experiments = list_campaign_experiments(connection, resumed_campaign_id)
        snapshot = build_archive_snapshot(experiments)
        replace_campaign_archive_rows(
            connection,
            resumed_campaign_id,
            archive_rows_from_snapshot(resumed_campaign_id, snapshot, created_at=timestamp),
        )
        write_archive_snapshot(paths, resumed_campaign_id, snapshot)

    payload = {
        "ok": True,
        "campaign_id": campaign_id,
        "status": _resume_status(
            inspected_running=len(running),
            finalized=finalized,
            requeued=requeued,
            synthesized_experiments=synthesized_experiments,
        ),
        "inspected_running_proposals": len(running),
        "touched_campaigns": sorted(touched_campaigns),
        "finalized_proposals": finalized,
        "requeued_proposals": requeued,
        "recovered_experiments": recovered_experiments,
        "synthesized_experiments": synthesized_experiments,
        "notes": _resume_notes(
            inspected_running=len(running),
            finalized=finalized,
            requeued=requeued,
            synthesized_experiments=synthesized_experiments,
        ),
    }
    return payload


def _latest_terminal_experiment(connection, proposal_id: str) -> dict[str, Any] | None:
    experiments = list_proposal_experiments(connection, proposal_id)
    for row in experiments:
        if str(row.get("status")) in TERMINAL_EXPERIMENT_STATUSES:
            return row
    return None


def _latest_run_root_for_proposal(runs_root: Path, proposal_id: str) -> Path | None:
    if not runs_root.exists():
        return None

    candidates: list[tuple[str, Path]] = []
    for run_root in sorted(runs_root.iterdir()):
        if not run_root.is_dir():
            continue
        proposal_path = run_root / "proposal.json"
        manifest_path = run_root / "manifest.json"
        if not proposal_path.exists() or not manifest_path.exists():
            continue
        try:
            proposal_payload = read_json(proposal_path)
            manifest = read_json(manifest_path)
        except Exception:
            continue
        if str(proposal_payload.get("proposal_id")) != proposal_id:
            continue
        candidates.append((str(manifest.get("created_at") or manifest.get("experiment_id") or run_root.name), run_root))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _recover_or_interrupt_run(connection, *, paths, run_root: Path, proposal: dict[str, Any], campaign: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(run_root / "manifest.json")
    experiment_id = str(manifest["experiment_id"])
    summary_path = run_root / "summary.json"
    summary = _load_terminal_summary(summary_path)
    synthesized_summary = False
    if summary is None:
        summary = _synthesize_interrupted_summary(run_root=run_root, manifest=manifest, proposal=proposal, campaign=campaign)
        write_json(summary_path, summary)
        synthesized_summary = True

    artifact_index = _rebuild_artifact_index(run_root, experiment_id, summary)
    upsert_experiment(
        connection,
        summary,
        artifact_root=run_root,
        disposition=summary.get("disposition"),
        crash_class=summary.get("crash_class"),
    )
    replace_artifacts(connection, artifact_index)
    return {
        "experiment_id": experiment_id,
        "proposal_status": _proposal_terminal_status(summary),
        "synthesized_summary": synthesized_summary,
    }


def _load_terminal_summary(summary_path: Path) -> dict[str, Any] | None:
    if not summary_path.exists():
        return None
    try:
        payload = read_json(summary_path)
    except Exception:
        return None
    if str(payload.get("status")) not in TERMINAL_EXPERIMENT_STATUSES:
        return None
    return payload


def _synthesize_interrupted_summary(
    *,
    run_root: Path,
    manifest: dict[str, Any],
    proposal: dict[str, Any],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    checkpoint_path = run_root / "checkpoints" / "pre_eval.safetensors"
    created_at = str(manifest.get("created_at") or utc_now_iso())
    return {
        "experiment_id": manifest["experiment_id"],
        "proposal_id": manifest.get("proposal_id"),
        "campaign_id": manifest["campaign_id"],
        "lane": manifest["lane"],
        "status": "failed",
        "disposition": None,
        "crash_class": "interrupted",
        "proposal_family": proposal.get("family"),
        "proposal_kind": proposal.get("kind"),
        "complexity_cost": proposal.get("complexity_cost"),
        "primary_metric_name": campaign["primary_metric"]["name"],
        "primary_metric_value": 0.0,
        "metric_delta": None,
        "budget_seconds": int(manifest.get("time_budget_seconds") or 1),
        "train_seconds": 0.0,
        "eval_seconds": 0.0,
        "compile_seconds": 0.0,
        "tokens_processed": 0,
        "tokens_per_second": 0.0,
        "steady_state_mfu": None,
        "peak_vram_gb": 0.0,
        "param_count": None,
        "backend": str(manifest.get("backend") or "unknown"),
        "device_profile": str(manifest.get("device_profile") or "unknown"),
        "seed": int(manifest.get("seed") or 0),
        "config_fingerprint": str(manifest.get("config_fingerprint") or "unknown"),
        "git_commit": str(manifest.get("parent_commit") or "unknown"),
        "warnings": ["run was interrupted before a terminal summary was committed"],
        "checkpoint_path": str(checkpoint_path) if checkpoint_path.exists() else None,
        "summary_version": "1.0.0",
        "started_at": created_at,
        "ended_at": utc_now_iso(),
    }


def _rebuild_artifact_index(run_root: Path, experiment_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    status = str(summary.get("status") or "failed")
    summary_retention = "full" if status == "completed" else "crash_exemplar"
    log_retention = "discardable" if status == "completed" else "crash_exemplar"

    artifacts = [
        build_artifact_record(run_root, "manifest.json", kind="manifest", retention_class="full"),
        build_artifact_record(run_root, "proposal.json", kind="proposal", retention_class="full"),
        build_artifact_record(run_root, "config.json", kind="config", retention_class="full"),
        build_artifact_record(run_root, "env.json", kind="env", retention_class="full"),
        build_artifact_record(run_root, "stdout.log", kind="stdout", retention_class=log_retention),
        build_artifact_record(run_root, "stderr.log", kind="stderr", retention_class=log_retention),
        build_artifact_record(run_root, "summary.json", kind="summary", retention_class=summary_retention),
    ]
    checkpoint_retention = _checkpoint_retention(summary)
    for relative_path in ("checkpoints/pre_eval.safetensors", "checkpoints/pre_eval.meta.json"):
        if (run_root / relative_path).exists():
            artifacts.append(
                build_artifact_record(
                    run_root,
                    relative_path,
                    kind="checkpoint",
                    retention_class=checkpoint_retention,
                )
            )
    return write_artifact_index(run_root, experiment_id, artifacts)


def _checkpoint_retention(summary: dict[str, Any]) -> str:
    if str(summary.get("status")) != "completed":
        return "crash_exemplar"
    if str(summary.get("disposition")) in {"promoted", "archived"}:
        return "promoted"
    return "discardable"


def _proposal_terminal_status(summary: dict[str, Any]) -> str:
    if str(summary.get("status")) != "completed":
        return "discarded"
    disposition = str(summary.get("disposition") or "")
    if disposition in {"promoted", "archived", "discarded"}:
        return disposition
    return "completed"


def _proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("proposal_json")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resume_notes(
    *,
    inspected_running: int,
    finalized: list[dict[str, str]],
    requeued: list[dict[str, str]],
    synthesized_experiments: list[str],
) -> list[str]:
    notes: list[str] = []
    if inspected_running == 0:
        notes.append("No proposals were still marked running, so resume was a clean no-op.")
        return notes
    if finalized:
        notes.append(f"Normalized {len(finalized)} running proposal(s) to a terminal status from persisted ledger/artifact state.")
    if synthesized_experiments:
        notes.append(f"Synthesized interrupted failure summaries for {len(synthesized_experiments)} orphaned run(s).")
    if requeued:
        notes.append(f"Requeued {len(requeued)} proposal(s) so the next session can continue without losing progress.")
    if not notes:
        notes.append("Resume inspected running proposals and found no additional work to normalize.")
    return notes


def _resume_status(
    *,
    inspected_running: int,
    finalized: list[dict[str, str]],
    requeued: list[dict[str, str]],
    synthesized_experiments: list[str],
) -> str:
    if inspected_running == 0:
        return "noop"
    if requeued or synthesized_experiments:
        return "recovered"
    if finalized:
        return "settled"
    return "noop"


__all__ = ["resume_interrupted_state"]
