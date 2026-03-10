from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from .utils.fs import ensure_directory

REPO_MARKERS = (
    Path("pyproject.toml"),
    Path("README.md"),
    Path("docs") / "runbook.md",
    Path("schemas") / "campaign.schema.json",
    Path("sql") / "001_ledger.sql",
)


@dataclass(frozen=True)
class LabPaths:
    repo_root: Path
    docs_root: Path
    campaigns_root: Path
    schemas_root: Path
    sql_root: Path
    templates_root: Path
    artifacts_root: Path
    runs_root: Path
    reports_root: Path
    proposals_root: Path
    archive_root: Path
    cache_root: Path
    campaign_cache_root: Path
    raw_cache_root: Path
    worktrees_root: Path
    db_path: Path
    env_file: Path

    def managed_roots(self) -> tuple[Path, ...]:
        return (
            self.artifacts_root,
            self.runs_root,
            self.reports_root,
            self.proposals_root,
            self.archive_root,
            self.cache_root,
            self.campaign_cache_root,
            self.raw_cache_root,
            self.worktrees_root,
            self.db_path.parent,
        )


def discover_repo_root(start: Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in REPO_MARKERS):
            return candidate
    raise ValueError(f"could not discover repo root from {current}")


def build_paths(settings: "LabSettings") -> LabPaths:
    repo_root = settings.repo_root.resolve()
    artifacts_root = settings.artifacts_root.resolve()
    cache_root = settings.cache_root.resolve()
    worktrees_root = settings.worktrees_root.resolve()
    db_path = settings.db_path.resolve()
    return LabPaths(
        repo_root=repo_root,
        docs_root=repo_root / "docs",
        campaigns_root=repo_root / "campaigns",
        schemas_root=repo_root / "schemas",
        sql_root=repo_root / "sql",
        templates_root=repo_root / "templates",
        artifacts_root=artifacts_root,
        runs_root=artifacts_root / "runs",
        reports_root=artifacts_root / "reports",
        proposals_root=artifacts_root / "proposals",
        archive_root=artifacts_root / "archive",
        cache_root=cache_root,
        campaign_cache_root=cache_root / "campaigns",
        raw_cache_root=cache_root / "raw",
        worktrees_root=worktrees_root,
        db_path=db_path,
        env_file=repo_root / ".lab.env",
    )


def ensure_managed_roots(paths: LabPaths) -> list[Path]:
    created: list[Path] = []
    for root in paths.managed_roots():
        if not root.exists():
            ensure_directory(root)
            created.append(root)
    return created


def experiment_root(paths: LabPaths, experiment_id: str) -> Path:
    return paths.runs_root / experiment_id


def report_root(paths: LabPaths, campaign_id: str, report_date: date | str) -> Path:
    date_part = report_date.isoformat() if isinstance(report_date, date) else str(report_date)
    return paths.reports_root / date_part / campaign_id


def missing_repo_markers(repo_root: Path) -> list[str]:
    missing: list[str] = []
    for marker in REPO_MARKERS:
        candidate = repo_root / marker
        if not candidate.exists():
            missing.append(str(marker))
    return missing


def stringify_paths(paths: Iterable[Path]) -> list[str]:
    return [str(path) for path in paths]


def resolve_managed_path(paths: LabPaths, configured_path: str | Path) -> Path:
    candidate = Path(configured_path)
    if candidate.is_absolute():
        return candidate
    if candidate.parts:
        if candidate.parts[0] == "artifacts":
            return paths.artifacts_root.joinpath(*candidate.parts[1:])
        if candidate.parts[0] == ".worktrees":
            return paths.worktrees_root.joinpath(*candidate.parts[1:])
    return paths.repo_root / candidate
