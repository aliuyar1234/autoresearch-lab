from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..proposals import normalize_proposal_payload
from .records import (
    artifact_rows_from_index,
    campaign_row_from_manifest,
    experiment_row_from_summary,
    proposal_row_from_payload,
    validation_review_row_from_payload,
)


def upsert_campaign(connection, manifest: dict[str, Any], *, timestamp: str) -> None:
    row = campaign_row_from_manifest(manifest, timestamp=timestamp)
    connection.execute(
        """
        INSERT INTO campaigns (
            campaign_id, version, title, active, comparability_group, primary_metric_name,
            manifest_json, created_at, updated_at
        ) VALUES (
            :campaign_id, :version, :title, :active, :comparability_group, :primary_metric_name,
            :manifest_json, :created_at, :updated_at
        )
        ON CONFLICT(campaign_id) DO UPDATE SET
            version=excluded.version,
            title=excluded.title,
            active=excluded.active,
            comparability_group=excluded.comparability_group,
            primary_metric_name=excluded.primary_metric_name,
            manifest_json=excluded.manifest_json,
            updated_at=excluded.updated_at
        """,
        row,
    )


def upsert_proposal(connection, proposal: dict[str, Any], *, updated_at: str | None = None) -> None:
    row = proposal_row_from_payload(proposal, updated_at=updated_at)
    connection.execute(
        """
        INSERT INTO proposals (
            proposal_id, campaign_id, family, kind, lane, status, generator, parent_ids_json,
            complexity_cost, hypothesis, rationale, config_overrides_json, retrieval_event_id,
            idea_signature, mutation_paths_json, proposal_json,
            created_at, updated_at
        ) VALUES (
            :proposal_id, :campaign_id, :family, :kind, :lane, :status, :generator, :parent_ids_json,
            :complexity_cost, :hypothesis, :rationale, :config_overrides_json, :retrieval_event_id,
            :idea_signature, :mutation_paths_json, :proposal_json,
            :created_at, :updated_at
        )
        ON CONFLICT(proposal_id) DO UPDATE SET
            campaign_id=excluded.campaign_id,
            family=excluded.family,
            kind=excluded.kind,
            lane=excluded.lane,
            status=excluded.status,
            generator=excluded.generator,
            parent_ids_json=excluded.parent_ids_json,
            complexity_cost=excluded.complexity_cost,
            hypothesis=excluded.hypothesis,
            rationale=excluded.rationale,
            config_overrides_json=excluded.config_overrides_json,
            retrieval_event_id=excluded.retrieval_event_id,
            idea_signature=excluded.idea_signature,
            mutation_paths_json=excluded.mutation_paths_json,
            proposal_json=excluded.proposal_json,
            updated_at=excluded.updated_at
        """,
        row,
    )


def set_proposal_status(connection, proposal_id: str, status: str, *, updated_at: str) -> None:
    row = connection.execute("SELECT proposal_json FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
    proposal_json = None
    if row and row["proposal_json"]:
        try:
            payload = normalize_proposal_payload(json.loads(row["proposal_json"]))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            payload["status"] = status
            proposal_json = json.dumps(payload, sort_keys=True)
    connection.execute(
        "UPDATE proposals SET status = ?, proposal_json = COALESCE(?, proposal_json), updated_at = ? WHERE proposal_id = ?",
        (status, proposal_json, updated_at, proposal_id),
    )


def upsert_experiment(
    connection,
    summary: dict[str, Any],
    *,
    artifact_root: Path,
    disposition: str | None = None,
    crash_class: str | None = None,
) -> None:
    row = experiment_row_from_summary(summary, artifact_root=artifact_root, disposition=disposition, crash_class=crash_class)
    connection.execute(
        """
        INSERT INTO experiments (
            experiment_id, proposal_id, campaign_id, lane, status, eval_split, run_purpose,
            replay_source_experiment_id, validation_state, validation_review_id, idea_signature, disposition, crash_class,
            seed, git_commit, device_profile, backend, proposal_family, proposal_kind, complexity_cost,
            budget_seconds, primary_metric_name, primary_metric_value, metric_delta,
            tokens_per_second, peak_vram_gb, summary_path, artifact_root,
            started_at, ended_at, created_at, updated_at
        ) VALUES (
            :experiment_id, :proposal_id, :campaign_id, :lane, :status, :eval_split, :run_purpose,
            :replay_source_experiment_id, :validation_state, :validation_review_id, :idea_signature, :disposition, :crash_class,
            :seed, :git_commit, :device_profile, :backend, :proposal_family, :proposal_kind, :complexity_cost,
            :budget_seconds, :primary_metric_name, :primary_metric_value, :metric_delta,
            :tokens_per_second, :peak_vram_gb, :summary_path, :artifact_root,
            :started_at, :ended_at, :created_at, :updated_at
        )
        ON CONFLICT(experiment_id) DO UPDATE SET
            status=excluded.status,
            eval_split=excluded.eval_split,
            run_purpose=excluded.run_purpose,
            replay_source_experiment_id=excluded.replay_source_experiment_id,
            validation_state=excluded.validation_state,
            validation_review_id=excluded.validation_review_id,
            idea_signature=excluded.idea_signature,
            disposition=excluded.disposition,
            crash_class=excluded.crash_class,
            seed=excluded.seed,
            git_commit=excluded.git_commit,
            device_profile=excluded.device_profile,
            backend=excluded.backend,
            proposal_family=excluded.proposal_family,
            proposal_kind=excluded.proposal_kind,
            complexity_cost=excluded.complexity_cost,
            budget_seconds=excluded.budget_seconds,
            primary_metric_name=excluded.primary_metric_name,
            primary_metric_value=excluded.primary_metric_value,
            metric_delta=excluded.metric_delta,
            tokens_per_second=excluded.tokens_per_second,
            peak_vram_gb=excluded.peak_vram_gb,
            summary_path=excluded.summary_path,
            artifact_root=excluded.artifact_root,
            started_at=excluded.started_at,
            ended_at=excluded.ended_at,
            updated_at=excluded.updated_at
        """,
        row,
    )


def set_experiment_review_state(
    connection,
    experiment_id: str,
    *,
    disposition: str | None = None,
    validation_state: str | None = None,
    validation_review_id: str | None = None,
    updated_at: str,
) -> None:
    existing = connection.execute(
        "SELECT disposition, validation_state, validation_review_id FROM experiments WHERE experiment_id = ?",
        (experiment_id,),
    ).fetchone()
    if existing is None:
        raise FileNotFoundError(f"experiment not found: {experiment_id}")
    connection.execute(
        """
        UPDATE experiments
        SET disposition = ?,
            validation_state = ?,
            validation_review_id = ?,
            updated_at = ?
        WHERE experiment_id = ?
        """,
        (
            disposition if disposition is not None else existing["disposition"],
            validation_state if validation_state is not None else existing["validation_state"],
            validation_review_id if validation_review_id is not None else existing["validation_review_id"],
            updated_at,
            experiment_id,
        ),
    )


def upsert_validation_review(connection, payload: dict[str, Any]) -> None:
    row = validation_review_row_from_payload(payload)
    connection.execute(
        """
        INSERT INTO validation_reviews (
            review_id, source_experiment_id, campaign_id, review_type, eval_split,
            candidate_experiment_ids_json, comparator_experiment_ids_json, seed_list_json,
            candidate_metric_median, comparator_metric_median, delta_median,
            decision, reason, review_json, created_at, updated_at
        ) VALUES (
            :review_id, :source_experiment_id, :campaign_id, :review_type, :eval_split,
            :candidate_experiment_ids_json, :comparator_experiment_ids_json, :seed_list_json,
            :candidate_metric_median, :comparator_metric_median, :delta_median,
            :decision, :reason, :review_json, :created_at, :updated_at
        )
        ON CONFLICT(review_id) DO UPDATE SET
            source_experiment_id=excluded.source_experiment_id,
            campaign_id=excluded.campaign_id,
            review_type=excluded.review_type,
            eval_split=excluded.eval_split,
            candidate_experiment_ids_json=excluded.candidate_experiment_ids_json,
            comparator_experiment_ids_json=excluded.comparator_experiment_ids_json,
            seed_list_json=excluded.seed_list_json,
            candidate_metric_median=excluded.candidate_metric_median,
            comparator_metric_median=excluded.comparator_metric_median,
            delta_median=excluded.delta_median,
            decision=excluded.decision,
            reason=excluded.reason,
            review_json=excluded.review_json,
            updated_at=excluded.updated_at
        """,
        row,
    )


def replace_artifacts(connection, artifact_index: dict[str, Any]) -> None:
    experiment_id = artifact_index["experiment_id"]
    connection.execute("DELETE FROM artifacts WHERE experiment_id = ?", (experiment_id,))
    for row in artifact_rows_from_index(artifact_index):
        connection.execute(
            """
            INSERT INTO artifacts (
                experiment_id, kind, relative_path, sha256, size_bytes,
                retention_class, content_type, created_at
            ) VALUES (
                :experiment_id, :kind, :relative_path, :sha256, :size_bytes,
                :retention_class, :content_type, :created_at
            )
            """,
            row,
        )


def get_experiment(connection, experiment_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
    return dict(row) if row else None


def get_proposal(connection, proposal_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
    return dict(row) if row else None


def get_validation_review(connection, review_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM validation_reviews WHERE review_id = ?", (review_id,)).fetchone()
    if not row:
        return None
    return _decode_validation_review_row(dict(row))


def list_campaign_proposals(connection, campaign_id: str, *, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM proposals WHERE campaign_id = ?"
    params: list[Any] = [campaign_id]
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)
    query += " ORDER BY created_at ASC, proposal_id ASC"
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_campaign_experiments(connection, campaign_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT
            e.*,
            p.proposal_json,
            p.parent_ids_json,
            p.config_overrides_json,
            p.generator AS proposal_generator,
            p.status AS proposal_status
        FROM experiments AS e
        LEFT JOIN proposals AS p ON p.proposal_id = e.proposal_id
        WHERE e.campaign_id = ?
        ORDER BY e.started_at DESC, e.experiment_id DESC
    """
    params: list[Any] = [campaign_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def list_prior_experiments(connection, campaign_id: str, lane: str, *, exclude_experiment_id: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT * FROM experiments
        WHERE campaign_id = ? AND lane = ? AND status = 'completed'
          AND COALESCE(run_purpose, 'search') IN ('search', 'baseline')
    """
    params: list[Any] = [campaign_id, lane]
    if exclude_experiment_id is not None:
        query += " AND experiment_id != ?"
        params.append(exclude_experiment_id)
    query += " ORDER BY ended_at ASC, experiment_id ASC"
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_retrieval_event(connection, payload: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO retrieval_events (
            retrieval_event_id, campaign_id, proposal_id, family, lane, query_text,
            query_tags_json, query_payload_json, created_at
        ) VALUES (
            :retrieval_event_id, :campaign_id, :proposal_id, :family, :lane, :query_text,
            :query_tags_json, :query_payload_json, :created_at
        )
        ON CONFLICT(retrieval_event_id) DO UPDATE SET
            campaign_id=excluded.campaign_id,
            proposal_id=excluded.proposal_id,
            family=excluded.family,
            lane=excluded.lane,
            query_text=excluded.query_text,
            query_tags_json=excluded.query_tags_json,
            query_payload_json=excluded.query_payload_json
        """,
        {
            "retrieval_event_id": payload["retrieval_event_id"],
            "campaign_id": payload["campaign_id"],
            "proposal_id": payload.get("proposal_id"),
            "family": payload.get("family"),
            "lane": payload.get("lane"),
            "query_text": payload["query_text"],
            "query_tags_json": json.dumps(payload.get("query_tags", []), sort_keys=True),
            "query_payload_json": json.dumps(payload.get("query_payload", {}), sort_keys=True),
            "created_at": payload["created_at"],
        },
    )


def replace_retrieval_event_items(connection, *, retrieval_event_id: str, items: list[dict[str, Any]], created_at: str) -> None:
    connection.execute("DELETE FROM retrieval_event_items WHERE retrieval_event_id = ?", (retrieval_event_id,))
    for item in items:
        connection.execute(
            """
            INSERT INTO retrieval_event_items (
                retrieval_event_id, memory_id, rank, score, selected_for_context, role_hint, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retrieval_event_id,
                item["memory_id"],
                int(item["rank"]),
                float(item["score"]),
                1 if bool(item.get("selected_for_context")) else 0,
                item.get("role_hint"),
                item.get("reason"),
                created_at,
            ),
        )


def replace_proposal_evidence_links(
    connection,
    *,
    proposal_id: str,
    retrieval_event_id: str | None,
    evidence: list[dict[str, Any]],
    created_at: str,
) -> None:
    connection.execute("DELETE FROM proposal_evidence_links WHERE proposal_id = ?", (proposal_id,))
    for item in evidence:
        connection.execute(
            """
            INSERT INTO proposal_evidence_links (
                proposal_id, memory_id, retrieval_event_id, role, score, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                item["memory_id"],
                retrieval_event_id,
                item["role"],
                float(item.get("score") or 0.0),
                item["reason"],
                created_at,
            ),
        )


def list_memory_records(
    connection,
    *,
    campaign_id: str | None = None,
    comparability_group: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM memory_records WHERE 1 = 1"
    params: list[Any] = []
    if campaign_id is not None and comparability_group is not None:
        query += " AND (campaign_id = ? OR comparability_group = ?)"
        params.extend([campaign_id, comparability_group])
    elif campaign_id is not None:
        query += " AND campaign_id = ?"
        params.append(campaign_id)
    elif comparability_group is not None:
        query += " AND comparability_group = ?"
        params.append(comparability_group)
    query += " ORDER BY updated_at DESC, memory_id ASC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [_decode_memory_row(dict(row)) for row in rows]


def get_memory_records_by_ids(connection, memory_ids: list[str]) -> list[dict[str, Any]]:
    ids = [str(item) for item in memory_ids if str(item)]
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT * FROM memory_records
        WHERE memory_id IN ({placeholders})
        ORDER BY updated_at DESC, memory_id ASC
        """,
        ids,
    ).fetchall()
    decoded_rows = [_decode_memory_row(dict(row)) for row in rows]
    by_id = {row["memory_id"]: row for row in decoded_rows}
    return [by_id[memory_id] for memory_id in ids if memory_id in by_id]


def list_proposal_evidence_links(connection, proposal_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT proposal_id, memory_id, retrieval_event_id, role, score, reason, created_at
        FROM proposal_evidence_links
        WHERE proposal_id = ?
        ORDER BY id ASC
        """,
        (proposal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_retrieval_event(connection, retrieval_event_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM retrieval_events WHERE retrieval_event_id = ?", (retrieval_event_id,)).fetchone()
    if row is None:
        return None
    items = connection.execute(
        """
        SELECT memory_id, rank, score, selected_for_context, role_hint, reason
        FROM retrieval_event_items
        WHERE retrieval_event_id = ?
        ORDER BY rank ASC, id ASC
        """,
        (retrieval_event_id,),
    ).fetchall()
    payload = dict(row)
    return {
        "retrieval_event_id": payload["retrieval_event_id"],
        "campaign_id": payload["campaign_id"],
        "proposal_id": payload["proposal_id"],
        "family": payload["family"],
        "lane": payload["lane"],
        "query_text": payload["query_text"],
        "query_tags": json.loads(payload["query_tags_json"] or "[]"),
        "query_payload": json.loads(payload["query_payload_json"] or "{}"),
        "items": [
            {
                "memory_id": item["memory_id"],
                "rank": int(item["rank"]),
                "score": float(item["score"]),
                "selected_for_context": bool(item["selected_for_context"]),
                "role_hint": item["role_hint"],
                "reason": item["reason"],
            }
            for item in items
        ],
        "created_at": payload["created_at"],
    }


def list_validation_reviews(
    connection,
    *,
    campaign_id: str | None = None,
    source_experiment_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM validation_reviews WHERE 1 = 1"
    params: list[Any] = []
    if campaign_id is not None:
        query += " AND campaign_id = ?"
        params.append(campaign_id)
    if source_experiment_id is not None:
        query += " AND source_experiment_id = ?"
        params.append(source_experiment_id)
    query += " ORDER BY created_at DESC, review_id DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [_decode_validation_review_row(dict(row)) for row in rows]


def list_proposal_experiments(connection, proposal_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM experiments
        WHERE proposal_id = ?
        ORDER BY started_at DESC, experiment_id DESC
        """,
        (proposal_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_running_proposals(connection, *, campaign_id: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM proposals WHERE status = 'running'"
    params: list[Any] = []
    if campaign_id is not None:
        query += " AND campaign_id = ?"
        params.append(campaign_id)
    query += " ORDER BY updated_at ASC, proposal_id ASC"
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def replace_champion_rows(
    connection,
    *,
    campaign_id: str,
    experiment_id: str,
    keep: bool,
    reason: str,
    rank_bucket: str,
    created_at: str,
) -> None:
    connection.execute("DELETE FROM champions WHERE experiment_id = ?", (experiment_id,))
    if not keep:
        return
    connection.execute(
        """
        INSERT INTO champions (campaign_id, experiment_id, reason, rank_bucket, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (campaign_id, experiment_id, reason, rank_bucket, created_at),
    )


def replace_campaign_archive_rows(connection, campaign_id: str, rows: list[dict[str, Any]]) -> None:
    connection.execute("DELETE FROM champions WHERE campaign_id = ?", (campaign_id,))
    for row in rows:
        connection.execute(
            """
            INSERT INTO champions (campaign_id, experiment_id, reason, rank_bucket, created_at)
            VALUES (:campaign_id, :experiment_id, :reason, :rank_bucket, :created_at)
            """,
            row,
        )


def list_archive_rows(connection, campaign_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT campaign_id, experiment_id, reason, rank_bucket, created_at
        FROM champions
        WHERE campaign_id = ?
        ORDER BY rank_bucket ASC, created_at DESC, experiment_id ASC
        """,
        (campaign_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_artifact_rows(
    connection,
    *,
    retention_classes: list[str] | None = None,
    campaign_id: str | None = None,
    experiment_id: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            a.id,
            a.experiment_id,
            a.kind,
            a.relative_path,
            a.sha256,
            a.size_bytes,
            a.retention_class,
            a.content_type,
            a.created_at,
            e.artifact_root,
            e.campaign_id,
            e.summary_path,
            e.status AS experiment_status
        FROM artifacts AS a
        INNER JOIN experiments AS e ON e.experiment_id = a.experiment_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if retention_classes:
        placeholders = ", ".join("?" for _ in retention_classes)
        query += f" AND a.retention_class IN ({placeholders})"
        params.extend(retention_classes)
    if campaign_id is not None:
        query += " AND e.campaign_id = ?"
        params.append(campaign_id)
    if experiment_id is not None:
        query += " AND a.experiment_id = ?"
        params.append(experiment_id)
    query += " ORDER BY a.created_at ASC, a.id ASC"
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def delete_artifact_rows(connection, artifact_ids: list[int]) -> None:
    if not artifact_ids:
        return
    placeholders = ", ".join("?" for _ in artifact_ids)
    connection.execute(f"DELETE FROM artifacts WHERE id IN ({placeholders})", artifact_ids)


def upsert_daily_report(
    connection,
    *,
    campaign_id: str,
    report_date: str,
    report_path: str,
    report_json_path: str,
    run_count: int,
    promoted_count: int,
    failed_count: int,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO daily_reports (
            campaign_id, report_date, report_path, report_json_path,
            run_count, promoted_count, failed_count, created_at
        ) VALUES (
            :campaign_id, :report_date, :report_path, :report_json_path,
            :run_count, :promoted_count, :failed_count, :created_at
        )
        ON CONFLICT(campaign_id, report_date) DO UPDATE SET
            report_path=excluded.report_path,
            report_json_path=excluded.report_json_path,
            run_count=excluded.run_count,
            promoted_count=excluded.promoted_count,
            failed_count=excluded.failed_count,
            created_at=excluded.created_at
        """,
        {
            "campaign_id": campaign_id,
            "report_date": report_date,
            "report_path": report_path,
            "report_json_path": report_json_path,
            "run_count": int(run_count),
            "promoted_count": int(promoted_count),
            "failed_count": int(failed_count),
            "created_at": created_at,
        },
    )


def list_daily_reports(connection, campaign_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT campaign_id, report_date, report_path, report_json_path,
               run_count, promoted_count, failed_count, created_at
        FROM daily_reports
        WHERE campaign_id = ?
        ORDER BY report_date DESC, created_at DESC
    """
    params: list[Any] = [campaign_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_latest_daily_report(connection, campaign_id: str) -> dict[str, Any] | None:
    rows = list_daily_reports(connection, campaign_id, limit=1)
    return rows[0] if rows else None


def upsert_agent_session(connection, payload: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO agent_sessions (
            session_id, campaign_id, status, operator_mode, started_at, ended_at,
            hours_budget, max_runs_budget, max_structured_runs_budget, max_code_runs_budget,
            allow_confirm, seed_policy, backend, device_profile, queue_refills, run_count,
            structured_run_count, code_run_count, confirm_run_count, validation_review_count,
            report_checkpoint_count, self_review_count, lane_switch_count, last_lane, stop_reason,
            session_manifest_path, retrospective_json_path, report_json_path, session_summary_json,
            created_at, updated_at
        ) VALUES (
            :session_id, :campaign_id, :status, :operator_mode, :started_at, :ended_at,
            :hours_budget, :max_runs_budget, :max_structured_runs_budget, :max_code_runs_budget,
            :allow_confirm, :seed_policy, :backend, :device_profile, :queue_refills, :run_count,
            :structured_run_count, :code_run_count, :confirm_run_count, :validation_review_count,
            :report_checkpoint_count, :self_review_count, :lane_switch_count, :last_lane, :stop_reason,
            :session_manifest_path, :retrospective_json_path, :report_json_path, :session_summary_json,
            :created_at, :updated_at
        )
        ON CONFLICT(session_id) DO UPDATE SET
            campaign_id=excluded.campaign_id,
            status=excluded.status,
            operator_mode=excluded.operator_mode,
            started_at=excluded.started_at,
            ended_at=excluded.ended_at,
            hours_budget=excluded.hours_budget,
            max_runs_budget=excluded.max_runs_budget,
            max_structured_runs_budget=excluded.max_structured_runs_budget,
            max_code_runs_budget=excluded.max_code_runs_budget,
            allow_confirm=excluded.allow_confirm,
            seed_policy=excluded.seed_policy,
            backend=excluded.backend,
            device_profile=excluded.device_profile,
            queue_refills=excluded.queue_refills,
            run_count=excluded.run_count,
            structured_run_count=excluded.structured_run_count,
            code_run_count=excluded.code_run_count,
            confirm_run_count=excluded.confirm_run_count,
            validation_review_count=excluded.validation_review_count,
            report_checkpoint_count=excluded.report_checkpoint_count,
            self_review_count=excluded.self_review_count,
            lane_switch_count=excluded.lane_switch_count,
            last_lane=excluded.last_lane,
            stop_reason=excluded.stop_reason,
            session_manifest_path=excluded.session_manifest_path,
            retrospective_json_path=excluded.retrospective_json_path,
            report_json_path=excluded.report_json_path,
            session_summary_json=excluded.session_summary_json,
            updated_at=excluded.updated_at
        """,
        {
            **payload,
            "allow_confirm": 1 if bool(payload.get("allow_confirm")) else 0,
            "session_summary_json": json.dumps(payload.get("session_summary", {}), sort_keys=True),
        },
    )


def append_agent_session_event(
    connection,
    *,
    session_id: str,
    event_type: str,
    created_at: str,
    lane: str | None = None,
    proposal_id: str | None = None,
    experiment_id: str | None = None,
    review_id: str | None = None,
    report_path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO agent_session_events (
            session_id, event_type, lane, proposal_id, experiment_id, review_id,
            report_path, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            event_type,
            lane,
            proposal_id,
            experiment_id,
            review_id,
            report_path,
            json.dumps(payload or {}, sort_keys=True),
            created_at,
        ),
    )


def get_agent_session(connection, session_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    return _decode_agent_session_row(dict(row))


def list_agent_sessions(connection, campaign_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT *
        FROM agent_sessions
        WHERE campaign_id = ?
        ORDER BY started_at DESC, updated_at DESC, session_id DESC
    """
    params: list[Any] = [campaign_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [_decode_agent_session_row(dict(row)) for row in rows]


def list_agent_session_events(connection, session_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, session_id, event_type, lane, proposal_id, experiment_id, review_id, report_path, payload_json, created_at
        FROM agent_session_events
        WHERE session_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (session_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "session_id": row["session_id"],
            "event_type": row["event_type"],
            "lane": row["lane"],
            "proposal_id": row["proposal_id"],
            "experiment_id": row["experiment_id"],
            "review_id": row["review_id"],
            "report_path": row["report_path"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _decode_validation_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": row["review_id"],
        "source_experiment_id": row["source_experiment_id"],
        "campaign_id": row["campaign_id"],
        "review_type": row["review_type"],
        "eval_split": row["eval_split"],
        "candidate_experiment_ids": json.loads(row["candidate_experiment_ids_json"] or "[]"),
        "comparator_experiment_ids": json.loads(row["comparator_experiment_ids_json"] or "[]"),
        "seed_list": json.loads(row["seed_list_json"] or "[]"),
        "candidate_metric_median": row["candidate_metric_median"],
        "comparator_metric_median": row["comparator_metric_median"],
        "delta_median": row["delta_median"],
        "decision": row["decision"],
        "reason": row["reason"],
        "review": json.loads(row["review_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _decode_agent_session_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "campaign_id": row["campaign_id"],
        "status": row["status"],
        "operator_mode": row["operator_mode"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "hours_budget": row["hours_budget"],
        "max_runs_budget": row["max_runs_budget"],
        "max_structured_runs_budget": row["max_structured_runs_budget"],
        "max_code_runs_budget": row["max_code_runs_budget"],
        "allow_confirm": bool(row["allow_confirm"]),
        "seed_policy": row["seed_policy"],
        "backend": row["backend"],
        "device_profile": row["device_profile"],
        "queue_refills": int(row["queue_refills"]),
        "run_count": int(row["run_count"]),
        "structured_run_count": int(row["structured_run_count"]),
        "code_run_count": int(row["code_run_count"]),
        "confirm_run_count": int(row["confirm_run_count"]),
        "validation_review_count": int(row["validation_review_count"]),
        "report_checkpoint_count": int(row["report_checkpoint_count"]),
        "self_review_count": int(row["self_review_count"]),
        "lane_switch_count": int(row["lane_switch_count"]),
        "last_lane": row["last_lane"],
        "stop_reason": row["stop_reason"],
        "session_manifest_path": row["session_manifest_path"],
        "retrospective_json_path": row["retrospective_json_path"],
        "report_json_path": row["report_json_path"],
        "session_summary": json.loads(row["session_summary_json"] or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _decode_memory_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": row["memory_id"],
        "campaign_id": row.get("campaign_id"),
        "comparability_group": row.get("comparability_group"),
        "record_type": row["record_type"],
        "source_kind": row["source_kind"],
        "source_ref": row["source_ref"],
        "family": row.get("family"),
        "lane": row.get("lane"),
        "eval_split": row.get("eval_split"),
        "outcome_label": row.get("outcome_label"),
        "title": row["title"],
        "summary": row["summary"],
        "tags": json.loads(row.get("tags_json") or "[]"),
        "payload": json.loads(row.get("payload_json") or "{}"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
