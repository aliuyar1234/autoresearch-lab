# Upstream snapshot notes

These files are included so Codex can inspect the upstream baseline without needing a network call.

Snapshot contents:
- `README.md`
- `program.md`
- `prepare.py`
- `train.py`
- `pyproject.toml`

Use them to:
- preserve the original taste
- understand the baseline constants and behaviors
- verify `base_2k` campaign parity decisions

Do not treat them as frozen forever.
If upstream materially changes and the project intentionally resyncs, refresh this snapshot and update `docs/references/upstream-baseline-summary.md`.
