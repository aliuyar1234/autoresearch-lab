from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .ledger.db import apply_migrations, connect, list_schema_versions
from .ledger.queries import list_agent_sessions, list_artifact_rows, list_daily_reports, list_running_proposals
from .paths import missing_repo_markers
from .utils.fs import is_within

RETAINED_RETENTION_CLASSES = ("full", "promoted", "champion", "crash_exemplar", "report", "campaign_asset")


def run_doctor(paths, *, campaign_id: str | None = None) -> dict[str, Any]:
    apply_migrations(paths.db_path, paths.sql_root)
    findings: list[dict[str, Any]] = []
    schema_versions = list_schema_versions(paths.db_path)
    repo_marker_gaps = missing_repo_markers(paths.repo_root)

    connection = connect(paths.db_path)
    try:
        integrity_row = connection.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "unknown"
        findings.extend(_managed_root_findings(paths))
        findings.extend(_schema_findings(schema_versions=schema_versions, repo_marker_gaps=repo_marker_gaps))
        findings.extend(_missing_artifact_findings(connection, paths=paths, campaign_id=campaign_id))
        findings.extend(_missing_report_findings(connection, campaign_id=campaign_id))
        findings.extend(_missing_session_findings(connection, campaign_id=campaign_id))
        findings.extend(_running_proposal_findings(connection, campaign_id=campaign_id))
        findings.extend(_worktree_findings(paths.worktrees_root))
    finally:
        connection.close()

    if integrity != "ok":
        findings.append(
            {
                "type": "db_integrity",
                "severity": "error",
                "message": f"PRAGMA integrity_check returned {integrity}",
            }
        )

    findings = [_annotate_problem_class(item) for item in findings]

    counts = Counter(str(item["severity"]) for item in findings)
    problem_counts = Counter(str(item["problem_class"]) for item in findings)
    return {
        "ok": counts.get("error", 0) == 0 and integrity == "ok",
        "campaign_id": campaign_id,
        "integrity_check": integrity,
        "schema_versions": schema_versions,
        "counts": {
            "error": counts.get("error", 0),
            "warning": counts.get("warning", 0),
            "info": counts.get("info", 0),
        },
        "problem_counts": {
            "artifact": problem_counts.get("artifact", 0),
            "config": problem_counts.get("config", 0),
            "env": problem_counts.get("env", 0),
            "ledger": problem_counts.get("ledger", 0),
            "run": problem_counts.get("run", 0),
            "user": problem_counts.get("user", 0),
        },
        "findings": findings,
    }


def _managed_root_findings(paths) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for root in paths.managed_roots():
        if root.exists():
            continue
        findings.append(
            {
                "type": "managed_root_missing",
                "severity": "warning",
                "path": str(root),
                "message": f"Managed root is missing: {root}",
            }
        )
    return findings


def _schema_findings(*, schema_versions: list[str], repo_marker_gaps: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if "001_ledger" not in schema_versions:
        findings.append(
            {
                "type": "schema_version_missing",
                "severity": "error",
                "message": "Required ledger schema version 001_ledger is missing.",
            }
        )
    for marker in repo_marker_gaps:
        findings.append(
            {
                "type": "repo_marker_missing",
                "severity": "warning",
                "path": marker,
                "message": f"Repo marker is missing: {marker}",
            }
        )
    return findings


def _missing_artifact_findings(connection, *, paths, campaign_id: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    rows = list_artifact_rows(
        connection,
        retention_classes=list(RETAINED_RETENTION_CLASSES),
        campaign_id=campaign_id,
    )
    for row in rows:
        artifact_path = Path(str(row["artifact_root"])) / str(row["relative_path"])
        if not is_within(artifact_path, paths.artifacts_root):
            findings.append(
                {
                    "type": "artifact_outside_managed_root",
                    "severity": "error",
                    "experiment_id": str(row["experiment_id"]),
                    "path": str(artifact_path),
                    "message": f"Retained artifact escapes the managed artifacts root: {artifact_path}",
                }
            )
            continue
        if artifact_path.exists():
            continue
        findings.append(
            {
                "type": "missing_artifact",
                "severity": "error",
                "experiment_id": str(row["experiment_id"]),
                "retention_class": str(row["retention_class"]),
                "path": str(artifact_path),
                "message": f"Retained artifact is missing: {artifact_path}",
            }
        )
    return findings


def _missing_report_findings(connection, *, campaign_id: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if campaign_id is None:
        campaign_rows = connection.execute("SELECT DISTINCT campaign_id FROM daily_reports ORDER BY campaign_id ASC").fetchall()
        campaigns = [str(row["campaign_id"]) for row in campaign_rows]
    else:
        campaigns = [campaign_id]
    for report_campaign_id in campaigns:
        for row in list_daily_reports(connection, report_campaign_id):
            for key in ("report_path", "report_json_path"):
                report_path = row.get(key)
                if not report_path:
                    continue
                path = Path(str(report_path))
                if path.exists():
                    continue
                findings.append(
                    {
                        "type": "missing_report_artifact",
                        "severity": "error",
                        "campaign_id": report_campaign_id,
                        "report_date": str(row["report_date"]),
                        "path": str(path),
                        "message": f"Daily report artifact is missing: {path}",
                    }
                )
    return findings


def _running_proposal_findings(connection, *, campaign_id: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in list_running_proposals(connection, campaign_id=campaign_id):
        findings.append(
            {
                "type": "proposal_still_running",
                "severity": "warning",
                "proposal_id": str(row["proposal_id"]),
                "campaign_id": str(row["campaign_id"]),
                "message": f"Proposal is still marked running and may need resume handling: {row['proposal_id']}",
            }
        )
    return findings


def _worktree_findings(worktrees_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not worktrees_root.exists():
        return findings
    for entry in sorted(worktrees_root.iterdir()):
        if entry.is_symlink() and not entry.exists():
            findings.append(
                {
                    "type": "broken_worktree_link",
                    "severity": "warning",
                    "path": str(entry),
                    "message": f"Broken worktree link detected: {entry}",
                }
            )
            continue
        if not entry.is_dir():
            continue
        if (entry / ".git").exists():
            continue
        if (entry / "repo").is_dir():
            continue
        findings.append(
            {
                "type": "worktree_incomplete",
                "severity": "warning",
                "path": str(entry),
                "message": f"Worktree directory does not contain a .git entry: {entry}",
            }
        )
    return findings


def _missing_session_findings(connection, *, campaign_id: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if campaign_id is None:
        campaign_rows = connection.execute("SELECT DISTINCT campaign_id FROM agent_sessions ORDER BY campaign_id ASC").fetchall()
        campaigns = [str(row["campaign_id"]) for row in campaign_rows]
    else:
        campaigns = [campaign_id]
    for session_campaign_id in campaigns:
        for row in list_agent_sessions(connection, session_campaign_id):
            for key in ("session_manifest_path", "retrospective_json_path", "report_json_path"):
                path_value = row.get(key)
                if not path_value:
                    continue
                path = Path(str(path_value))
                if path.exists():
                    continue
                findings.append(
                    {
                        "type": "missing_session_artifact",
                        "severity": "error",
                        "campaign_id": session_campaign_id,
                        "session_id": str(row["session_id"]),
                        "path": str(path),
                        "message": f"Agent session artifact is missing: {path}",
                    }
                )
    return findings


def _annotate_problem_class(finding: dict[str, Any]) -> dict[str, Any]:
    problem_class = _problem_class_for_type(str(finding.get("type") or ""))
    return {
        **finding,
        "problem_class": problem_class,
    }


def _problem_class_for_type(finding_type: str) -> str:
    if finding_type in {"db_integrity", "schema_version_missing"}:
        return "ledger"
    if finding_type in {"missing_artifact", "missing_report_artifact", "missing_session_artifact", "artifact_outside_managed_root"}:
        return "artifact"
    if finding_type in {"proposal_still_running"}:
        return "run"
    if finding_type in {"repo_marker_missing"}:
        return "config"
    if finding_type in {"managed_root_missing", "broken_worktree_link", "worktree_incomplete"}:
        return "env"
    return "user"


__all__ = ["RETAINED_RETENTION_CLASSES", "run_doctor"]
