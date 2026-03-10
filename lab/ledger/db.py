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
        if sql_path.is_file():
            _apply_migration_file(connection, sql_path)
        elif sql_path.is_dir():
            applied_versions = _applied_versions(connection)
            for migration_path in _migration_paths(sql_path):
                version = _migration_version(migration_path)
                if version in applied_versions:
                    continue
                _apply_migration_file(connection, migration_path)
                applied_versions.add(version)
        else:
            raise FileNotFoundError(f"migration path does not exist: {sql_path}")
    finally:
        connection.close()
    return created


def list_schema_versions(db_path: Path) -> list[str]:
    connection = connect(db_path)
    try:
        try:
            rows = connection.execute("SELECT version FROM schema_migrations ORDER BY applied_at ASC, rowid ASC, version ASC").fetchall()
        except sqlite3.OperationalError:
            return []
        return [str(row["version"]) for row in rows]
    finally:
        connection.close()


def _migration_paths(sql_root: Path) -> list[Path]:
    return sorted(path for path in sql_root.glob("*.sql") if path.is_file())


def _applied_versions(connection: sqlite3.Connection) -> set[str]:
    try:
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {str(row["version"]) for row in rows}


def _migration_version(migration_path: Path) -> str:
    return migration_path.stem


def _apply_migration_file(connection: sqlite3.Connection, migration_path: Path) -> None:
    script = migration_path.read_text(encoding="utf-8")
    prelude, body = _split_prelude(script)
    version = _migration_version(migration_path)

    try:
        for statement in _iter_sql_statements(prelude):
            connection.execute(statement)
        connection.execute("BEGIN")
        for statement in _iter_sql_statements(body):
            connection.execute(statement)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
            (version,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _split_prelude(script: str) -> tuple[str, str]:
    prelude_lines: list[str] = []
    body_lines: list[str] = []
    in_body = False

    for line in script.splitlines(keepends=True):
        stripped = line.strip()
        if not in_body:
            if not stripped or stripped.startswith("--") or stripped.upper().startswith("PRAGMA "):
                prelude_lines.append(line)
                continue
            in_body = True
        body_lines.append(line)

    return "".join(prelude_lines), "".join(body_lines)


def _iter_sql_statements(script: str):
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if not sqlite3.complete_statement(buffer):
            continue
        statement = buffer.strip()
        buffer = ""
        if statement:
            yield statement
    trailing = buffer.strip()
    if trailing:
        yield trailing
