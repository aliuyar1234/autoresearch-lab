from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def apply_migrations(db_path: Path, sql_path: Path) -> bool:
    created = not db_path.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(db_path)
    try:
        connection.executescript(sql_path.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()
    return created


def list_schema_versions(db_path: Path) -> list[str]:
    connection = connect(db_path)
    try:
        try:
            rows = connection.execute("SELECT version FROM schema_migrations ORDER BY applied_at, version").fetchall()
        except sqlite3.OperationalError:
            return []
        return [str(row["version"]) for row in rows]
    finally:
        connection.close()
