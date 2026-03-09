from __future__ import annotations

import difflib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .paths import LabPaths
from .utils import is_within, read_json, utc_now_iso, write_json


class CodeProposalExportError(ValueError):
    pass


class CodeProposalImportError(ValueError):
    pass


def export_code_proposal_pack(
    *,
    paths: LabPaths,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    best_comparator: dict[str, Any] | None,
    parent_experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    if proposal.get("kind") != "code_patch":
        raise CodeProposalExportError("export-code-proposal currently requires a proposal with kind=code_patch")
    code_patch = proposal.get("code_patch")
    if not isinstance(code_patch, dict):
        raise CodeProposalExportError("code_patch proposal is missing the code_patch block")

    target_files = [str(item) for item in code_patch.get("target_files", [])]
    if not target_files:
        raise CodeProposalExportError("code_patch proposal must define at least one target file")

    pack_root = paths.proposals_root / proposal["proposal_id"] / "code_pack"
    context_root = pack_root / "context"
    files_root = context_root / "files"
    pack_root.mkdir(parents=True, exist_ok=True)
    context_root.mkdir(parents=True, exist_ok=True)
    files_root.mkdir(parents=True, exist_ok=True)

    write_json(pack_root / "proposal.json", proposal)
    (pack_root / "README.md").write_text(_render_readme(campaign, proposal, best_comparator), encoding="utf-8")
    (pack_root / "acceptance_criteria.md").write_text(_render_acceptance_criteria(proposal, target_files), encoding="utf-8")
    (pack_root / "target_files.txt").write_text("\n".join(target_files) + "\n", encoding="utf-8")
    (pack_root / "return_instructions.md").write_text(_render_return_instructions(campaign, proposal), encoding="utf-8")

    write_json(context_root / "campaign.json", campaign)
    if best_comparator is not None:
        write_json(context_root / "best_comparator.json", _strip_row(best_comparator))
    write_json(context_root / "parent_runs.json", [_strip_row(item) for item in parent_experiments])
    _copy_context_doc(paths.repo_root / "docs" / "product-specs" / "code-lane-pack.md", context_root / "code-lane-pack.md")
    _copy_context_doc(paths.repo_root / "docs" / "product-specs" / "proposal-format.md", context_root / "proposal-format.md")
    _copy_context_doc(paths.repo_root / "docs" / "product-specs" / "runner-contract.md", context_root / "runner-contract.md")
    copied_targets = _copy_target_files(paths.repo_root, files_root, target_files)

    return {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "pack_root": str(pack_root),
        "target_files": target_files,
        "copied_context_files": copied_targets,
        "files": sorted(
            str(path.relative_to(pack_root)).replace("\\", "/")
            for path in pack_root.rglob("*")
            if path.is_file()
        ),
    }


def import_code_proposal_result(
    *,
    paths: LabPaths,
    proposal: dict[str, Any],
    patch_path: Path | None = None,
    worktree_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if proposal.get("kind") != "code_patch":
        raise CodeProposalImportError("import-code-proposal currently requires a proposal with kind=code_patch")
    code_patch = proposal.get("code_patch")
    if not isinstance(code_patch, dict):
        raise CodeProposalImportError("code_patch proposal is missing the code_patch block")
    target_files = [str(item).replace("\\", "/") for item in code_patch.get("target_files", [])]
    if not target_files:
        raise CodeProposalImportError("code_patch proposal must define at least one target file")
    provided_sources = [patch_path is not None, worktree_path is not None]
    if sum(provided_sources) != 1:
        raise CodeProposalImportError("import-code-proposal requires exactly one of --patch-path or --worktree-path")

    imported_at = utc_now_iso()
    import_root = paths.proposals_root / proposal["proposal_id"] / "imports" / _safe_stamp(imported_at)
    files_root = import_root / "files"
    import_root.mkdir(parents=True, exist_ok=True)

    changed_files: list[str]
    deleted_files: list[str]
    return_kind: str
    source_path: Path
    patch_destination = import_root / "returned.patch"

    if patch_path is not None:
        source_path = patch_path.resolve()
        if not source_path.exists() or not source_path.is_file():
            raise CodeProposalImportError(f"patch file not found: {source_path}")
        patch_text = source_path.read_text(encoding="utf-8")
        changed_files, deleted_files = _parse_patch_paths(patch_text)
        _validate_allowlist(target_files, changed_files, deleted_files)
        patch_destination.write_text(patch_text, encoding="utf-8")
        return_kind = "patch"
    else:
        source_path = worktree_path.resolve()
        if not source_path.exists() or not source_path.is_dir():
            raise CodeProposalImportError(f"worktree path not found: {source_path}")
        diff_result = _diff_worktree(paths.repo_root, source_path)
        outside_allowlist = sorted(path for path in diff_result["changed"] if path not in set(target_files))
        if outside_allowlist:
            raise CodeProposalImportError(
                "returned worktree modified files outside the proposal allowlist: " + ", ".join(outside_allowlist[:10])
            )
        changed_files = sorted(path for path in diff_result["changed"] if path in set(target_files) and path not in diff_result["deleted"])
        deleted_files = sorted(path for path in diff_result["deleted"] if path in set(target_files))
        if not changed_files and not deleted_files:
            raise CodeProposalImportError("returned worktree did not modify any allowlisted files")
        files_root.mkdir(parents=True, exist_ok=True)
        for relative_path in changed_files:
            destination = files_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((source_path / relative_path).read_text(encoding="utf-8"), encoding="utf-8")
        patch_destination.write_text(
            _build_patch_from_worktree(paths.repo_root, source_path, changed_files=changed_files, deleted_files=deleted_files),
            encoding="utf-8",
        )
        return_kind = "worktree"

    if not changed_files and not deleted_files:
        raise CodeProposalImportError("returned code proposal did not contain any allowlisted changes")

    return_manifest = {
        "proposal_id": proposal["proposal_id"],
        "campaign_id": proposal["campaign_id"],
        "imported_at": imported_at,
        "return_kind": return_kind,
        "source_path": str(source_path),
        "patch_path": str(patch_destination),
        "import_root": str(import_root),
        "target_files": target_files,
        "changed_files": changed_files,
        "deleted_files": deleted_files,
    }
    write_json(import_root / "return_manifest.json", return_manifest)

    updated = json.loads(json.dumps(proposal))
    updated_code_patch = dict(code_patch)
    updated_code_patch.update(
        {
            "patch_path": str(patch_destination),
            "import_root": str(import_root),
            "imported_at": imported_at,
            "return_kind": return_kind,
            "imported_files": changed_files,
            "deleted_files": deleted_files,
        }
    )
    updated["code_patch"] = updated_code_patch
    updated["status"] = "queued"
    updated["generator"] = "imported"
    updated["notes"] = _append_note(updated.get("notes"), f"Imported {return_kind} return at {imported_at}.")

    payload = {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "import_root": str(import_root),
        "return_kind": return_kind,
        "patch_path": str(patch_destination),
        "changed_files": changed_files,
        "deleted_files": deleted_files,
    }
    return updated, payload


def code_proposal_ready(proposal: dict[str, Any]) -> bool:
    if proposal.get("kind") != "code_patch":
        return True
    code_patch = proposal.get("code_patch")
    if not isinstance(code_patch, dict):
        return False
    return bool(code_patch.get("patch_path") and code_patch.get("import_root"))


def prepare_code_patch_execution(paths: LabPaths, proposal: dict[str, Any], *, experiment_id: str) -> dict[str, Any] | None:
    if proposal.get("kind") != "code_patch":
        return None
    code_patch = proposal.get("code_patch")
    if not isinstance(code_patch, dict):
        raise CodeProposalImportError("code_patch proposal is missing the code_patch block")
    import_root_raw = code_patch.get("import_root")
    patch_path_raw = code_patch.get("patch_path")
    if not import_root_raw or not patch_path_raw:
        raise CodeProposalImportError("code_patch proposal has no imported return; run import-code-proposal first")

    import_root = Path(str(import_root_raw))
    return_manifest_path = import_root / "return_manifest.json"
    if not return_manifest_path.exists():
        raise CodeProposalImportError(f"import manifest not found: {return_manifest_path}")
    return_manifest = read_json(return_manifest_path)
    execution_root = paths.worktrees_root / experiment_id / "repo"
    shutil.copytree(paths.repo_root, execution_root, ignore=_copytree_ignore(paths))

    if str(return_manifest["return_kind"]) == "worktree":
        files_root = import_root / "files"
        for relative_path in return_manifest.get("changed_files", []):
            source = files_root / str(relative_path)
            if not source.exists():
                raise CodeProposalImportError(f"imported worktree file is missing from bundle: {source}")
            destination = execution_root / str(relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        for relative_path in return_manifest.get("deleted_files", []):
            destination = execution_root / str(relative_path)
            if destination.exists():
                destination.unlink()
    else:
        patch_path = Path(str(return_manifest["patch_path"]))
        _apply_patch_to_snapshot(execution_root, patch_path)

    write_json(execution_root / ".lab_code_patch_import.json", return_manifest)
    return {
        "execution_root": execution_root,
        "import_root": import_root,
        "return_manifest": return_manifest,
    }


def _render_readme(campaign: dict[str, Any], proposal: dict[str, Any], best_comparator: dict[str, Any] | None) -> str:
    comparator_line = "No current best comparator is recorded yet."
    if best_comparator is not None:
        comparator_line = (
            f"Current best comparator: {best_comparator['experiment_id']} "
            f"with {best_comparator['primary_metric_name']}={float(best_comparator['primary_metric_value']):.6f}."
        )
    return "\n".join(
        [
            f"# Code Proposal Pack: {proposal['proposal_id']}",
            "",
            f"Campaign: `{proposal['campaign_id']}`",
            f"Lane: `{proposal['lane']}`",
            f"Family: `{proposal['family']}`",
            "",
            "## Goal",
            proposal["hypothesis"],
            "",
            "## Constraints",
            "- Stay within the target file allowlist in `target_files.txt`.",
            "- Keep the proposal aligned with the same runner and scoring pipeline.",
            "- Do not change campaign comparability semantics.",
            "",
            "## Scoring",
            f"Primary metric: `{campaign['primary_metric']['name']}` ({campaign['primary_metric']['direction']}).",
            comparator_line,
            "",
            "## Return path",
            "Return a patch file, git commit, or worktree path exactly as described in `return_instructions.md`.",
        ]
    )


def _render_acceptance_criteria(proposal: dict[str, Any], target_files: list[str]) -> str:
    acceptance_summary = proposal["code_patch"]["acceptance_summary"]
    lines = [
        "# Acceptance Criteria",
        "",
        "## Functional acceptance",
        f"- {acceptance_summary}",
        "- The resulting run must still produce a structured `summary.json` through the existing runner.",
        "",
        "## Test expectations",
        "- Update or add the smallest relevant tests for the touched behavior.",
        "- Preserve existing passing tests unless the proposal explicitly changes the contract.",
        "",
        "## Non-goals",
        "- Do not redesign the whole lab architecture.",
        "- Do not bypass the existing scoring, archive, or report pipeline.",
        "",
        "## Allowed files",
    ]
    lines.extend(f"- `{path}`" for path in target_files)
    lines.extend(
        [
            "",
            "## Forbidden paths",
            "- Any file not listed in `target_files.txt` unless the change is strictly required for tests tied to those files.",
        ]
    )
    return "\n".join(lines)


def _render_return_instructions(campaign: dict[str, Any], proposal: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Return Instructions",
            "",
            "Accepted return formats:",
            "- patch file",
            "- worktree path",
            "",
            "The returned change will be executed by the same runner and scored by the same promotion logic.",
            "Current CLI import path supports `--patch-path` and `--worktree-path`.",
            "",
            f"Campaign: `{campaign['campaign_id']}`",
            f"Lane: `{proposal['lane']}`",
            f"Primary metric: `{campaign['primary_metric']['name']}`",
        ]
    )


def _copy_context_doc(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_target_files(repo_root: Path, files_root: Path, target_files: list[str]) -> list[str]:
    copied: list[str] = []
    for relative_path in target_files:
        source = (repo_root / relative_path).resolve()
        if not is_within(source, repo_root):
            continue
        destination = files_root / relative_path
        if not source.exists() or not source.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(relative_path)
    return copied


def _strip_row(row: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (str, int, float)) or value is None:
            payload[key] = value
            continue
        if isinstance(value, bytes):
            payload[key] = value.decode("utf-8", errors="replace")
            continue
        payload[key] = str(value)
    return payload


def _parse_patch_paths(patch_text: str) -> tuple[list[str], list[str]]:
    changed: list[str] = []
    deleted: list[str] = []
    current_path: str | None = None
    for line in patch_text.splitlines():
        if line.startswith("+++ "):
            candidate = _normalize_patch_path(line[4:].strip())
            if candidate is None:
                current_path = None
                continue
            current_path = candidate
            if candidate not in changed:
                changed.append(candidate)
        elif line.startswith("--- ") and line[4:].strip() == "/dev/null":
            current_path = None
        elif line.startswith("deleted file mode "):
            continue
        elif line.startswith("--- "):
            current_path = _normalize_patch_path(line[4:].strip())
        elif line.startswith("+++ /dev/null") and current_path is not None:
            if current_path not in deleted:
                deleted.append(current_path)
    if not changed and not deleted:
        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    path = _normalize_patch_path(parts[3])
                    if path and path not in changed:
                        changed.append(path)
    changed = [path for path in changed if path not in deleted]
    return sorted(changed), sorted(deleted)


def _normalize_patch_path(value: str) -> str | None:
    candidate = value.strip()
    if candidate in {"", "/dev/null"}:
        return None
    if candidate.startswith("a/") or candidate.startswith("b/"):
        candidate = candidate[2:]
    return candidate.replace("\\", "/")


def _validate_allowlist(target_files: list[str], changed_files: list[str], deleted_files: list[str]) -> None:
    allowed = set(target_files)
    touched = sorted(set(changed_files) | set(deleted_files))
    outside = [path for path in touched if path not in allowed]
    if outside:
        raise CodeProposalImportError("returned change touched files outside the proposal allowlist: " + ", ".join(outside[:10]))


def _diff_worktree(repo_root: Path, worktree_path: Path) -> dict[str, set[str]]:
    repo_files = _collect_relative_files(repo_root)
    worktree_files = _collect_relative_files(worktree_path)
    changed: set[str] = set()
    deleted: set[str] = set()
    for relative_path in sorted(repo_files | worktree_files):
        repo_file = repo_root / relative_path
        worktree_file = worktree_path / relative_path
        if relative_path not in worktree_files:
            deleted.add(relative_path)
            changed.add(relative_path)
            continue
        if relative_path not in repo_files:
            changed.add(relative_path)
            continue
        if repo_file.read_text(encoding="utf-8") != worktree_file.read_text(encoding="utf-8"):
            changed.add(relative_path)
    return {"changed": changed, "deleted": deleted}


def _collect_relative_files(root: Path) -> set[str]:
    collected: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", ".venv", "artifacts", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in relative.parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        collected.add(str(relative).replace("\\", "/"))
    return collected


def _build_patch_from_worktree(repo_root: Path, worktree_path: Path, *, changed_files: list[str], deleted_files: list[str]) -> str:
    parts: list[str] = []
    deleted_set = set(deleted_files)
    for relative_path in changed_files:
        repo_file = repo_root / relative_path
        worktree_file = worktree_path / relative_path
        before = repo_file.read_text(encoding="utf-8").splitlines(keepends=True) if repo_file.exists() else []
        after = worktree_file.read_text(encoding="utf-8").splitlines(keepends=True)
        parts.extend(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                n=3,
            )
        )
    for relative_path in deleted_files:
        repo_file = repo_root / relative_path
        before = repo_file.read_text(encoding="utf-8").splitlines(keepends=True) if repo_file.exists() else []
        parts.extend(
            difflib.unified_diff(
                before,
                [],
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                n=3,
            )
        )
    return "".join(parts)


def _append_note(existing: str | None, note: str) -> str:
    if not existing:
        return note
    return f"{existing}\n{note}"


def _safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z").replace("T", "_")


def _copytree_ignore(paths: LabPaths):
    artifact_parent = paths.artifacts_root.parent.resolve()
    worktree_parent = paths.worktrees_root.parent.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}}
        directory_path = Path(directory).resolve()
        for name in names:
            candidate = (directory_path / name).resolve()
            if candidate == paths.artifacts_root.resolve() or candidate == paths.worktrees_root.resolve():
                ignored.add(name)
                continue
            if directory_path == artifact_parent and candidate == paths.artifacts_root.resolve():
                ignored.add(name)
            if directory_path == worktree_parent and candidate == paths.worktrees_root.resolve():
                ignored.add(name)
        return ignored

    return ignore


def _apply_patch_to_snapshot(execution_root: Path, patch_path: Path) -> None:
    init = subprocess.run(
        ["git", "init", "-q"],
        cwd=execution_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if init.returncode != 0:
        raise CodeProposalImportError(init.stderr.strip() or "failed to initialize execution snapshot git metadata")
    check = subprocess.run(
        ["git", "apply", "--check", str(patch_path)],
        cwd=execution_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        raise CodeProposalImportError(check.stderr.strip() or "imported patch failed validation")
    apply = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=execution_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if apply.returncode != 0:
        raise CodeProposalImportError(apply.stderr.strip() or "imported patch could not be applied")


__all__ = [
    "CodeProposalExportError",
    "CodeProposalImportError",
    "code_proposal_ready",
    "export_code_proposal_pack",
    "import_code_proposal_result",
    "prepare_code_patch_execution",
]
