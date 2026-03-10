from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..proposals import normalize_proposal_payload
from ..utils import load_schema, validate_payload
from .models import memory_id_for


def ingest_experiment_memory(
    connection,
    *,
    paths,
    campaign: dict[str, Any],
    experiment: dict[str, Any],
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for payload in _memory_payloads_for_experiment(campaign=campaign, experiment=experiment):
        if _upsert_memory(connection, paths=paths, payload=payload):
            created += 1
        else:
            skipped += 1
    return created, skipped


def ingest_validation_review_memory(connection, *, paths, campaign: dict[str, Any], review: dict[str, Any]) -> tuple[int, int]:
    payload_core = {
        "review_type": review["review_type"],
        "decision": review["decision"],
        "eval_split": review["eval_split"],
        "delta_median": review.get("delta_median"),
    }
    payload = {
        "memory_id": memory_id_for(
            record_type="validation_review",
            source_kind="validation_review",
            source_ref=review["review_id"],
            payload_core=payload_core,
        ),
        "campaign_id": review["campaign_id"],
        "comparability_group": campaign.get("comparability_group"),
        "record_type": "validation_review",
        "source_kind": "validation_review",
        "source_ref": review["review_id"],
        "family": None,
        "lane": "confirm" if review["review_type"] == "confirm" else None,
        "eval_split": review["eval_split"],
        "outcome_label": review["decision"],
        "title": f"Validation review {review['review_id']} ({review['review_type']})",
        "summary": review["reason"],
        "tags": [review["review_type"], review["decision"], review["eval_split"]],
        "payload": {
            "source_experiment_id": review["source_experiment_id"],
            "candidate_experiment_ids": review.get("candidate_experiment_ids", []),
            "comparator_experiment_ids": review.get("comparator_experiment_ids", []),
            "delta_median": review.get("delta_median"),
        },
        "created_at": review["created_at"],
        "updated_at": review["updated_at"],
    }
    created = 1 if _upsert_memory(connection, paths=paths, payload=payload) else 0
    return created, 0 if created else 1


def ingest_report_memory(connection, *, paths, campaign: dict[str, Any], report: dict[str, Any], report_json_path: str) -> tuple[int, int]:
    created = 0
    skipped = 0
    notes = list(report.get("recommendations", {}).get("notes", []))
    for index, note in enumerate(notes):
        payload_core = {"note": note, "index": index}
        payload = {
            "memory_id": memory_id_for(
                record_type="report_note",
                source_kind="daily_report",
                source_ref=f"{report['campaign_id']}:{report['report_date']}:{index}",
                payload_core=payload_core,
            ),
            "campaign_id": report["campaign_id"],
            "comparability_group": campaign.get("comparability_group"),
            "record_type": "report_note",
            "source_kind": "daily_report",
            "source_ref": f"{report['campaign_id']}:{report['report_date']}:{index}",
            "family": None,
            "lane": None,
            "eval_split": None,
            "outcome_label": "note",
            "title": f"Report note {report['report_date']} #{index + 1}",
            "summary": note,
            "tags": ["report_note", "recommendation"],
            "payload": {
                "report_date": report["report_date"],
                "report_json_path": report_json_path,
                "note": note,
            },
            "created_at": report["generated_at"],
            "updated_at": report["generated_at"],
        }
        if _upsert_memory(connection, paths=paths, payload=payload):
            created += 1
        else:
            skipped += 1
    return created, skipped


def backfill_memory(
    connection,
    *,
    paths,
    campaign: dict[str, Any],
    experiments: list[dict[str, Any]],
    validation_reviews: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> dict[str, int]:
    created = 0
    skipped = 0
    sources_scanned = 0
    for experiment in experiments:
        sources_scanned += 1
        exp_created, exp_skipped = ingest_experiment_memory(connection, paths=paths, campaign=campaign, experiment=experiment)
        created += exp_created
        skipped += exp_skipped
    for review in validation_reviews:
        sources_scanned += 1
        review_created, review_skipped = ingest_validation_review_memory(connection, paths=paths, campaign=campaign, review=review)
        created += review_created
        skipped += review_skipped
    for report_row in reports:
        sources_scanned += 1
        report_path = Path(str(report_row["report_json_path"]))
        if not report_path.exists():
            continue
        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        report_created, report_skipped = ingest_report_memory(
            connection,
            paths=paths,
            campaign=campaign,
            report=report_payload,
            report_json_path=str(report_path),
        )
        created += report_created
        skipped += report_skipped
    return {
        "memory_created": created,
        "memory_skipped_existing": skipped,
        "retrieval_events_created": 0,
        "sources_scanned": sources_scanned,
    }


def _memory_payloads_for_experiment(*, campaign: dict[str, Any], experiment: dict[str, Any]) -> list[dict[str, Any]]:
    proposal_payload = normalize_proposal_payload(_proposal_payload(experiment))
    config_overrides = proposal_payload.get("config_overrides", {})
    mutation_paths = proposal_payload.get("mutation_paths", [])
    code_patch_lineage = _code_patch_lineage(proposal_payload)
    payloads: list[dict[str, Any]] = []
    if str(experiment.get("status")) == "completed":
        disposition = str(experiment.get("disposition") or "completed")
        payload_core = {
            "disposition": disposition,
            "primary_metric_value": experiment.get("primary_metric_value"),
            "run_purpose": experiment.get("run_purpose"),
            "eval_split": experiment.get("eval_split"),
            "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
        }
        payloads.append(
            {
                "memory_id": memory_id_for(
                    record_type="experiment_result",
                    source_kind="experiment",
                    source_ref=str(experiment["experiment_id"]),
                    payload_core=payload_core,
                ),
                "campaign_id": experiment["campaign_id"],
                "comparability_group": campaign.get("comparability_group"),
                "record_type": "experiment_result",
                "source_kind": "experiment",
                "source_ref": str(experiment["experiment_id"]),
                "family": experiment.get("proposal_family") or proposal_payload.get("family"),
                "lane": experiment.get("lane"),
                "eval_split": experiment.get("eval_split"),
                "outcome_label": disposition,
                "title": f"Experiment {experiment['experiment_id']} {disposition}",
                "summary": _completed_experiment_summary(experiment),
                "tags": _experiment_tags(experiment, proposal_payload),
                "payload": {
                    "proposal_id": experiment.get("proposal_id"),
                    "primary_metric_name": experiment.get("primary_metric_name"),
                    "primary_metric_value": experiment.get("primary_metric_value"),
                    "disposition": experiment.get("disposition"),
                    "validation_state": experiment.get("validation_state"),
                    "run_purpose": experiment.get("run_purpose"),
                    "config_overrides": config_overrides,
                    "mutation_paths": mutation_paths,
                    "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
                    "code_patch": code_patch_lineage,
                },
                "created_at": experiment.get("started_at") or experiment.get("created_at"),
                "updated_at": experiment.get("ended_at") or experiment.get("updated_at"),
            }
        )
        if disposition == "promoted":
            champion_core = {
                "experiment_id": experiment["experiment_id"],
                "primary_metric_value": experiment.get("primary_metric_value"),
                "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
            }
            payloads.append(
                {
                    "memory_id": memory_id_for(
                        record_type="champion_snapshot",
                        source_kind="champion",
                        source_ref=str(experiment["experiment_id"]),
                        payload_core=champion_core,
                    ),
                    "campaign_id": experiment["campaign_id"],
                    "comparability_group": campaign.get("comparability_group"),
                    "record_type": "champion_snapshot",
                    "source_kind": "champion",
                    "source_ref": str(experiment["experiment_id"]),
                    "family": experiment.get("proposal_family") or proposal_payload.get("family"),
                    "lane": experiment.get("lane"),
                    "eval_split": experiment.get("eval_split"),
                    "outcome_label": "promoted",
                    "title": f"Champion snapshot {experiment['experiment_id']}",
                    "summary": _completed_experiment_summary(experiment),
                    "tags": _experiment_tags(experiment, proposal_payload) + ["champion"],
                    "payload": {
                        "proposal_id": experiment.get("proposal_id"),
                        "primary_metric_value": experiment.get("primary_metric_value"),
                        "config_overrides": config_overrides,
                        "mutation_paths": mutation_paths,
                        "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
                        "code_patch": code_patch_lineage,
                    },
                    "created_at": experiment.get("started_at") or experiment.get("created_at"),
                    "updated_at": experiment.get("ended_at") or experiment.get("updated_at"),
                }
            )
    else:
        payload_core = {
            "crash_class": experiment.get("crash_class"),
            "run_purpose": experiment.get("run_purpose"),
            "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
        }
        payloads.append(
            {
                "memory_id": memory_id_for(
                    record_type="failure_autopsy",
                    source_kind="experiment",
                    source_ref=str(experiment["experiment_id"]),
                    payload_core=payload_core,
                ),
                "campaign_id": experiment["campaign_id"],
                "comparability_group": campaign.get("comparability_group"),
                "record_type": "failure_autopsy",
                "source_kind": "experiment",
                "source_ref": str(experiment["experiment_id"]),
                "family": experiment.get("proposal_family") or proposal_payload.get("family"),
                "lane": experiment.get("lane"),
                "eval_split": experiment.get("eval_split"),
                "outcome_label": "failed",
                "title": f"Failure autopsy {experiment['experiment_id']}",
                "summary": f"{experiment.get('crash_class') or 'unknown'} on {experiment.get('lane')} lane",
                "tags": _experiment_tags(experiment, proposal_payload) + [str(experiment.get("crash_class") or "unknown")],
                "payload": {
                    "proposal_id": experiment.get("proposal_id"),
                    "crash_class": experiment.get("crash_class"),
                    "validation_state": experiment.get("validation_state"),
                    "config_overrides": config_overrides,
                    "mutation_paths": mutation_paths,
                    "idea_signature": experiment.get("idea_signature") or proposal_payload.get("idea_signature"),
                    "code_patch": code_patch_lineage,
                },
                "created_at": experiment.get("started_at") or experiment.get("created_at"),
                "updated_at": experiment.get("ended_at") or experiment.get("updated_at"),
            }
        )
    return payloads


def _upsert_memory(connection, *, paths, payload: dict[str, Any]) -> bool:
    validate_payload(payload, load_schema(paths.schemas_root / "memory_record.schema.json"))
    existing = connection.execute("SELECT 1 FROM memory_records WHERE memory_id = ?", (payload["memory_id"],)).fetchone()
    connection.execute(
        """
        INSERT INTO memory_records (
            memory_id, campaign_id, comparability_group, record_type, source_kind, source_ref,
            family, lane, eval_split, outcome_label, title, summary, tags_json, payload_json,
            created_at, updated_at
        ) VALUES (
            :memory_id, :campaign_id, :comparability_group, :record_type, :source_kind, :source_ref,
            :family, :lane, :eval_split, :outcome_label, :title, :summary, :tags_json, :payload_json,
            :created_at, :updated_at
        )
        ON CONFLICT(memory_id) DO UPDATE SET
            campaign_id=excluded.campaign_id,
            comparability_group=excluded.comparability_group,
            record_type=excluded.record_type,
            source_kind=excluded.source_kind,
            source_ref=excluded.source_ref,
            family=excluded.family,
            lane=excluded.lane,
            eval_split=excluded.eval_split,
            outcome_label=excluded.outcome_label,
            title=excluded.title,
            summary=excluded.summary,
            tags_json=excluded.tags_json,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
        {
            **payload,
            "tags_json": json.dumps(payload.get("tags", []), sort_keys=True),
            "payload_json": json.dumps(payload.get("payload", {}), sort_keys=True),
        },
    )
    return existing is None


def _proposal_payload(experiment: dict[str, Any]) -> dict[str, Any]:
    raw = experiment.get("proposal_json")
    if not raw:
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def _completed_experiment_summary(experiment: dict[str, Any]) -> str:
    metric_name = str(experiment.get("primary_metric_name") or "metric")
    metric_value = experiment.get("primary_metric_value")
    metric_text = "n/a" if metric_value is None else f"{float(metric_value):.6f}"
    return f"{experiment.get('proposal_family') or 'manual'} {experiment.get('lane')} {experiment.get('disposition') or 'completed'} with {metric_name}={metric_text}"


def _experiment_tags(experiment: dict[str, Any], proposal_payload: dict[str, Any]) -> list[str]:
    tags = {
        str(experiment.get("proposal_family") or proposal_payload.get("family") or "manual"),
        str(experiment.get("proposal_kind") or proposal_payload.get("kind") or "structured"),
        str(experiment.get("lane") or "unknown"),
        str(experiment.get("eval_split") or "search_val"),
        str(experiment.get("run_purpose") or "search"),
    }
    if experiment.get("disposition"):
        tags.add(str(experiment["disposition"]))
    if experiment.get("idea_signature") or proposal_payload.get("idea_signature"):
        tags.add(str(experiment.get("idea_signature") or proposal_payload.get("idea_signature")))
    return sorted(tag for tag in tags if tag)


def _code_patch_lineage(proposal_payload: dict[str, Any]) -> dict[str, Any] | None:
    code_patch = proposal_payload.get("code_patch")
    if not isinstance(code_patch, dict):
        return None
    return {
        "target_files": list(code_patch.get("target_files", [])),
        "imported_files": list(code_patch.get("imported_files", [])),
        "deleted_files": list(code_patch.get("deleted_files", [])),
        "return_kind": code_patch.get("return_kind"),
        "diff_stats": dict(code_patch.get("diff_stats", {})) if isinstance(code_patch.get("diff_stats"), dict) else {},
        "evidence_memory_ids": list(code_patch.get("evidence_memory_ids", [])),
        "validation_targets": (
            dict(code_patch.get("validation_targets", {}))
            if isinstance(code_patch.get("validation_targets"), dict)
            else {}
        ),
    }
