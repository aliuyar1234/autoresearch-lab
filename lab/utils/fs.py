from __future__ import annotations

from pathlib import Path


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def nearest_existing_parent(path: Path) -> Path:
    current = path if path.is_dir() else path.parent
    current = current.resolve()
    while not current.exists():
        if current.parent == current:
            raise ValueError(f"no existing parent found for {path}")
        current = current.parent
    return current


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
