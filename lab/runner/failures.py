from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CrashResult:
    crash_class: str
    reason: str
    excerpt: str


def classify_failure(
    *,
    stderr_text: str,
    stdout_text: str = "",
    preflight_ok: bool = True,
    interrupted: bool = False,
) -> CrashResult:
    return classify_crash(
        stderr_text=stderr_text,
        stdout_text=stdout_text,
        preflight_ok=preflight_ok,
        interrupted=interrupted,
    )


_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("preflight_failed", ("preflight failed", "missing campaign", "missing asset")),
    ("import_error", ("ImportError", "ModuleNotFoundError", "cannot import name")),
    ("compile_error", ("torch.compile", "inductor", "triton", "compile error")),
    ("oom_eval", ("out of memory during eval", "oom_eval", "cuda out of memory while evaluating")),
    ("oom_train", ("cuda out of memory", "cublas_status_alloc_failed", "oom_train")),
    ("timeout", ("timed out", "timeout", "deadline exceeded")),
    ("nan_or_inf", ("nan", "inf", "non-finite")),
    ("assertion_failure", ("AssertionError", "assert ", "assertion failed")),
    ("data_missing", ("file not found", "No such file or directory", "missing data")),
    ("asset_corrupt", ("hash mismatch", "corrupt", "invalid header")),
    ("backend_unavailable", ("backend unavailable", "not compiled with cuda", "unsupported backend")),
    ("interrupted", ("KeyboardInterrupt", "SIGINT", "interrupted by user")),
]


def classify_crash(
    stderr_text: str,
    stdout_text: str = "",
    *,
    preflight_ok: bool = True,
    interrupted: bool = False,
) -> CrashResult:
    if not preflight_ok:
        return CrashResult("preflight_failed", "preflight flag false", stderr_text[:240])

    if interrupted:
        excerpt = stderr_text[:240] or stdout_text[:240] or "interrupted"
        return CrashResult("interrupted", "runner interruption flag", excerpt)

    combined = "\n".join(part for part in [stderr_text, stdout_text] if part)
    match = _first_matching_rule(combined)
    if match:
        crash_class, needle = match
        excerpt = _excerpt_around(combined, needle)
        return CrashResult(crash_class, f"matched signature: {needle}", excerpt)

    excerpt = (stderr_text or stdout_text or "unknown failure")[:240]
    return CrashResult("unknown", "no signature matched", excerpt)


def _first_matching_rule(text: str) -> tuple[str, str] | None:
    lowered = text.lower()
    for crash_class, needles in _RULES:
        for needle in needles:
            if needle.lower() in lowered:
                return crash_class, needle
    return None


def _excerpt_around(text: str, needle: str, width: int = 240) -> str:
    index = text.lower().find(needle.lower())
    if index < 0:
        return text[:width]
    start = max(0, index - width // 3)
    end = min(len(text), start + width)
    return text[start:end]
