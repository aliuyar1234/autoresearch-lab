from __future__ import annotations

from reference_impl.crash_classifier import CrashResult, classify_crash


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
