from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_LIKELY_CAUSES = {
    "compile_error": ("Inductor/Triton codegen or compile setup problem.", True),
    "import_error": ("Missing Python dependency or broken environment.", True),
    "oom_train": ("Model/runtime shape exceeds training memory budget.", True),
    "oom_eval": ("Evaluation batch or checkpoint path exceeds memory budget.", True),
    "backend_unavailable": ("Selected backend is not healthy for this machine/shape.", True),
    "data_missing": ("Campaign assets or source files are missing.", True),
    "asset_corrupt": ("Cached campaign assets failed integrity checks.", True),
    "timeout": ("Run budget or kernel progress was insufficient.", False),
    "nan_or_inf": ("Numerical instability in training or eval.", True),
    "assertion_failure": ("An explicit invariant in code was violated.", True),
    "unknown": ("No known failure signature matched.", False),
    "interrupted": ("Session was interrupted by the operator.", False),
}


def build_crash_summary(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in experiments:
        if str(row.get("status")) == "completed":
            continue
        crash_class = str(row.get("crash_class") or "unknown")
        grouped[crash_class].append(row)

    entries: list[dict[str, Any]] = []
    for crash_class, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        excerpt, example_experiment_id = _representative_excerpt(rows)
        likely_cause, suppress = _LIKELY_CAUSES.get(crash_class, ("Unknown failure mode.", False))
        times = sorted(str(row.get("ended_at") or row.get("started_at") or "") for row in rows)
        entries.append(
            {
                "crash_class": crash_class,
                "count": len(rows),
                "first_occurrence": times[0] if times else None,
                "last_occurrence": times[-1] if times else None,
                "typical_excerpt": excerpt,
                "likely_cause": likely_cause,
                "suppress_similar": suppress,
                "example_experiment_id": example_experiment_id,
            }
        )

    return {
        "total_failed_runs": sum(item["count"] for item in entries),
        "entries": entries,
    }


def render_crash_summary_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Crash Summary", ""]
    if not payload["entries"]:
        lines.append("No failed runs were included in this report window.")
        lines.append("")
        return "\n".join(lines)
    for entry in payload["entries"]:
        lines.extend(
            [
                f"## {entry['crash_class']}",
                "",
                f"- Count: {entry['count']}",
                f"- First occurrence: {entry['first_occurrence'] or 'n/a'}",
                f"- Last occurrence: {entry['last_occurrence'] or 'n/a'}",
                f"- Example experiment: {entry['example_experiment_id'] or 'n/a'}",
                f"- Likely cause: {entry['likely_cause']}",
                f"- Suppress similar proposals: {'yes' if entry['suppress_similar'] else 'no'}",
                "- Typical excerpt:",
                f"  {entry['typical_excerpt'] or 'n/a'}",
                "",
            ]
        )
    return "\n".join(lines)


def _representative_excerpt(rows: list[dict[str, Any]]) -> tuple[str, str | None]:
    excerpts: list[tuple[str, str | None]] = []
    for row in rows:
        artifact_root = row.get("artifact_root")
        if artifact_root:
            stderr_path = Path(str(artifact_root)) / "stderr.log"
            stdout_path = Path(str(artifact_root)) / "stdout.log"
            for candidate in (stderr_path, stdout_path):
                if candidate.exists():
                    text = candidate.read_text(encoding="utf-8").strip()
                    if text:
                        excerpts.append((text.splitlines()[0][:240], str(row["experiment_id"])))
                        break
        summary_path = row.get("summary_path")
        if summary_path and Path(str(summary_path)).exists():
            text = Path(str(summary_path)).read_text(encoding="utf-8").strip()
            if text:
                excerpts.append((text.splitlines()[0][:240], str(row["experiment_id"])))
    if not excerpts:
        return "", None
    counts = Counter(item[0] for item in excerpts)
    best_excerpt = counts.most_common(1)[0][0]
    for excerpt, experiment_id in excerpts:
        if excerpt == best_excerpt:
            return excerpt, experiment_id
    return excerpts[0]


__all__ = ["build_crash_summary", "render_crash_summary_markdown"]
