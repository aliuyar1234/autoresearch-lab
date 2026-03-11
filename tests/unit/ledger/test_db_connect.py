from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lab.ledger.db import apply_migrations, connect, list_schema_versions


REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_ROOT = REPO_ROOT / "sql"


def _pragma_value(connection: sqlite3.Connection, name: str):
    row = connection.execute(f"PRAGMA {name}").fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return row[0]
    return row[0]


class DbConnectTests(unittest.TestCase):
    def test_connect_sets_row_factory_and_pragmas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite3"

            connection = connect(db_path)
            try:
                row = connection.execute("SELECT 1 AS answer").fetchone()
                self.assertIsInstance(row, sqlite3.Row)
                self.assertEqual(int(row["answer"]), 1)
                self.assertEqual(int(_pragma_value(connection, "foreign_keys")), 1)
                self.assertEqual(int(_pragma_value(connection, "busy_timeout")), 5000)
                self.assertEqual(str(_pragma_value(connection, "journal_mode")).lower(), "wal")
            finally:
                connection.close()

    def test_apply_migrations_records_schema_versions_with_hardened_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "lab.sqlite3"

            created = apply_migrations(db_path, SQL_ROOT)

            self.assertTrue(created)
            self.assertEqual(
                list_schema_versions(db_path),
                ["001_ledger", "002_validation_reviews", "003_memory_evidence", "004_scheduler_semantics"],
            )

            connection = connect(db_path)
            try:
                self.assertEqual(int(_pragma_value(connection, "foreign_keys")), 1)
                self.assertEqual(int(_pragma_value(connection, "busy_timeout")), 5000)
                self.assertEqual(str(_pragma_value(connection, "journal_mode")).lower(), "wal")
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
