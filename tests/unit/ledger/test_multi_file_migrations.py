from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lab.ledger.db import apply_migrations, connect, list_schema_versions


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


class MultiFileMigrationTests(unittest.TestCase):
    def test_apply_directory_migrations_on_fresh_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            sql_root = temp_root / "sql"
            db_path = temp_root / "lab.sqlite3"
            sql_root.mkdir()

            (sql_root / "001_initial.sql").write_text(
                "\n".join(
                    [
                        "CREATE TABLE IF NOT EXISTS schema_migrations (",
                        "    version TEXT PRIMARY KEY,",
                        "    applied_at TEXT NOT NULL",
                        ");",
                        "CREATE TABLE IF NOT EXISTS alpha(id INTEGER PRIMARY KEY);",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sql_root / "002_followup.sql").write_text(
                "CREATE TABLE IF NOT EXISTS beta(id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )

            created = apply_migrations(db_path, sql_root)

            self.assertTrue(created)
            self.assertEqual(list_schema_versions(db_path), ["001_initial", "002_followup"])

            connection = connect(db_path)
            try:
                self.assertTrue(_table_exists(connection, "alpha"))
                self.assertTrue(_table_exists(connection, "beta"))
            finally:
                connection.close()

    def test_directory_mode_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            sql_root = temp_root / "sql"
            db_path = temp_root / "lab.sqlite3"
            sql_root.mkdir()

            (sql_root / "001_initial.sql").write_text(
                "\n".join(
                    [
                        "CREATE TABLE IF NOT EXISTS schema_migrations (",
                        "    version TEXT PRIMARY KEY,",
                        "    applied_at TEXT NOT NULL",
                        ");",
                        "CREATE TABLE IF NOT EXISTS alpha(id INTEGER PRIMARY KEY);",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sql_root / "002_followup.sql").write_text(
                "CREATE TABLE IF NOT EXISTS beta(id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )

            first_created = apply_migrations(db_path, sql_root)
            second_created = apply_migrations(db_path, sql_root)

            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(list_schema_versions(db_path), ["001_initial", "002_followup"])

            connection = connect(db_path)
            try:
                row = connection.execute("SELECT COUNT(*) AS count FROM schema_migrations").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["count"]), 2)
            finally:
                connection.close()

    def test_legacy_file_mode_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            db_path = temp_root / "lab.sqlite3"
            migration_path = temp_root / "001_legacy.sql"

            migration_path.write_text(
                "\n".join(
                    [
                        "CREATE TABLE IF NOT EXISTS schema_migrations (",
                        "    version TEXT PRIMARY KEY,",
                        "    applied_at TEXT NOT NULL",
                        ");",
                        "CREATE TABLE IF NOT EXISTS legacy_table(id INTEGER PRIMARY KEY);",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            first_created = apply_migrations(db_path, migration_path)
            second_created = apply_migrations(db_path, migration_path)

            self.assertTrue(first_created)
            self.assertFalse(second_created)
            self.assertEqual(list_schema_versions(db_path), ["001_legacy"])

            connection = connect(db_path)
            try:
                self.assertTrue(_table_exists(connection, "legacy_table"))
                row = connection.execute("SELECT COUNT(*) AS count FROM schema_migrations").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["count"]), 1)
            finally:
                connection.close()

    def test_failed_migration_does_not_mark_later_versions_as_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            sql_root = temp_root / "sql"
            db_path = temp_root / "lab.sqlite3"
            sql_root.mkdir()

            (sql_root / "001_initial.sql").write_text(
                "\n".join(
                    [
                        "CREATE TABLE IF NOT EXISTS schema_migrations (",
                        "    version TEXT PRIMARY KEY,",
                        "    applied_at TEXT NOT NULL",
                        ");",
                        "CREATE TABLE IF NOT EXISTS alpha(id INTEGER PRIMARY KEY);",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sql_root / "002_broken.sql").write_text(
                "\n".join(
                    [
                        "CREATE TABLE broken_one(id INTEGER PRIMARY KEY);",
                        "CREATE TABLE missing_comma(id INTEGER PRIMARY KEY name TEXT);",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sql_root / "003_later.sql").write_text(
                "CREATE TABLE IF NOT EXISTS later_table(id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )

            with self.assertRaises(sqlite3.Error):
                apply_migrations(db_path, sql_root)

            self.assertEqual(list_schema_versions(db_path), ["001_initial"])

            connection = connect(db_path)
            try:
                self.assertTrue(_table_exists(connection, "alpha"))
                self.assertFalse(_table_exists(connection, "broken_one"))
                self.assertFalse(_table_exists(connection, "later_table"))
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
