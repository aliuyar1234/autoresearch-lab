from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .records import artifact_rows_from_index, campaign_row_from_manifest, experiment_row_from_summary, proposal_row_from_payload


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
            complexity_cost, hypothesis, rationale, config_overrides_json, proposal_json,
            created_at, updated_at
        ) VALUES (
            :proposal_id, :campaign_id, :family, :kind, :lane, :status, :generator, :parent_ids_json,
            :complexity_cost, :hypothesis, :rationale, :config_overrides_json, :proposal_json,
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
            payload = json.loads(row["proposal_json"])
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
            experiment_id, proposal_id, campaign_id, lane, status, disposition, crash_class,
            seed, git_commit, device_profile, backend, proposal_family, proposal_kind, complexity_cost,
            budget_seconds, primary_metric_name, primary_metric_value, metric_delta,
            tokens_per_second, peak_vram_gb, summary_path, artifact_root,
            started_at, ended_at, created_at, updated_at
        ) VALUES (
            :experiment_id, :proposal_id, :campaign_id, :lane, :status, :disposition, :crash_class,
            :seed, :git_commit, :device_profile, :backend, :proposal_family, :proposal_kind, :complexity_cost,
            :budget_seconds, :primary_metric_name, :primary_metric_value, :metric_delta,
            :tokens_per_second, :peak_vram_gb, :summary_path, :artifact_root,
            :started_at, :ended_at, :created_at, :updated_at
        )
        ON CONFLICT(experiment_id) DO UPDATE SET
            status=excluded.status,
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
    """
    params: list[Any] = [campaign_id, lane]
    if exclude_experiment_id is not None:
        query += " AND experiment_id != ?"
        params.append(exclude_experiment_id)
    query += " ORDER BY ended_at ASC, experiment_id ASC"
    rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


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
