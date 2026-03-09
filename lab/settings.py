from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .paths import discover_repo_root, missing_repo_markers

ENV_KEYS = {
    "repo_root": "LAB_REPO_ROOT",
    "artifacts_root": "LAB_ARTIFACTS_ROOT",
    "worktrees_root": "LAB_WORKTREES_ROOT",
    "db_path": "LAB_DB_PATH",
    "cache_root": "LAB_CACHE_ROOT",
}


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class LabSettings:
    repo_root: Path
    artifacts_root: Path
    worktrees_root: Path
    db_path: Path
    cache_root: Path


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _resolve_path_value(raw: str | None, repo_root: Path, default: Path) -> Path:
    if raw is None or raw == "":
        return default
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _pick_value(
    cli_value: str | os.PathLike[str] | None,
    env_key: str,
    env: Mapping[str, str],
    env_file_values: Mapping[str, str],
) -> str | None:
    if cli_value is not None:
        return str(cli_value)
    if env_key in env:
        return env[env_key]
    return env_file_values.get(env_key)


def load_settings(
    *,
    repo_root: str | os.PathLike[str] | None = None,
    artifacts_root: str | os.PathLike[str] | None = None,
    worktrees_root: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
    cache_root: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> LabSettings:
    environment = dict(os.environ if env is None else env)

    repo_root_candidate: Path
    if repo_root is not None:
        repo_root_candidate = Path(repo_root).resolve()
    elif ENV_KEYS["repo_root"] in environment:
        repo_root_candidate = Path(environment[ENV_KEYS["repo_root"]]).resolve()
    else:
        repo_root_candidate = discover_repo_root(cwd)

    env_file_values = _parse_env_file(repo_root_candidate / ".lab.env")
    repo_root_value = _pick_value(repo_root, ENV_KEYS["repo_root"], environment, env_file_values)
    if repo_root_value is not None:
        repo_root_candidate = Path(repo_root_value).resolve()

    if not repo_root_candidate.exists():
        raise SettingsError(f"repo root does not exist: {repo_root_candidate}")

    missing_markers = missing_repo_markers(repo_root_candidate)
    if missing_markers:
        joined = ", ".join(missing_markers)
        raise SettingsError(f"repo root is missing required lab files: {joined}")

    default_artifacts_root = repo_root_candidate / "artifacts"
    default_worktrees_root = repo_root_candidate / ".worktrees"

    resolved_artifacts_root = _resolve_path_value(
        _pick_value(artifacts_root, ENV_KEYS["artifacts_root"], environment, env_file_values),
        repo_root_candidate,
        default_artifacts_root,
    )
    default_cache_root = resolved_artifacts_root / "cache"
    default_db_path = resolved_artifacts_root / "lab.sqlite3"
    resolved_worktrees_root = _resolve_path_value(
        _pick_value(worktrees_root, ENV_KEYS["worktrees_root"], environment, env_file_values),
        repo_root_candidate,
        default_worktrees_root,
    )
    resolved_cache_root = _resolve_path_value(
        _pick_value(cache_root, ENV_KEYS["cache_root"], environment, env_file_values),
        repo_root_candidate,
        default_cache_root,
    )
    resolved_db_path = _resolve_path_value(
        _pick_value(db_path, ENV_KEYS["db_path"], environment, env_file_values),
        repo_root_candidate,
        default_db_path,
    )

    return LabSettings(
        repo_root=repo_root_candidate,
        artifacts_root=resolved_artifacts_root,
        worktrees_root=resolved_worktrees_root,
        db_path=resolved_db_path,
        cache_root=resolved_cache_root,
    )
