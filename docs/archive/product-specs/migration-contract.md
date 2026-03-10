# Migration Contract

Autoresearch Lab uses plain SQL files under `sql/` as the ledger schema migration system.

## Source of truth

- Migration files live in `sql/`
- Migration version is the filename stem
- Example: `001_ledger.sql` becomes version `001_ledger`

## Runner behavior

`apply_migrations(db_path, sql_path)` supports two modes:

- file mode: if `sql_path` is a file, apply exactly that file
- directory mode: if `sql_path` is a directory, discover `*.sql`, sort them lexicographically, and apply only versions not yet recorded in `schema_migrations`

Directory mode is the normal runtime path for the lab.
File mode exists for backward compatibility and focused tests.

## Recording applied versions

- Applied versions are stored in `schema_migrations`
- The migration runner records the filename-stem version after a migration file succeeds
- Repeated directory-mode calls are idempotent because already-applied versions are skipped

## Ordering

- Migration discovery is lexicographic by filename
- New migrations must therefore use sortable numeric prefixes such as `002_*`, `003_*`, `004_*`

## Transaction expectations

- The runner uses one SQLite connection for a migration apply call
- Each migration file is applied independently
- If one migration fails, later migrations are not marked as applied

## Authoring rules for future migrations

- Add a new file under `sql/`; do not rewrite old migrations unless there is a very strong reason
- Keep migrations additive and reviewable
- Assume migrations may be invoked repeatedly through normal CLI entrypoints
- Prefer deterministic schema/data changes over runtime ad hoc SQL

## Operator expectations

These paths should stay safe to run repeatedly:

```bash
python -m lab.cli bootstrap
python -m lab.cli doctor
python -m lab.cli preflight --campaign base_2k
```

The migration substrate exists so later phases can add new schema files without editing `001_ledger.sql`.
