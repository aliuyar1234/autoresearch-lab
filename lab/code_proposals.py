from __future__ import annotations

import difflib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .proposals import normalize_proposal_payload
from .paths import LabPaths
from .semantics import is_validated_promotion
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
    evidence_records: list[dict[str, Any]] | None = None,
    retrieval_event: dict[str, Any] | None = None,
    validation_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal = normalize_proposal_payload(proposal)
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

    evidence_payload = _build_evidence_payload(
        proposal=proposal,
        parent_experiments=parent_experiments,
        evidence_records=evidence_records or [],
        retrieval_event=retrieval_event,
    )
    validation_payload = validation_targets or _build_validation_targets(
        campaign=campaign,
        proposal=proposal,
        best_comparator=best_comparator,
        parent_experiments=parent_experiments,
    )
    task_summary = _build_task_summary(
        campaign=campaign,
        proposal=proposal,
        best_comparator=best_comparator,
        evidence_payload=evidence_payload,
        validation_targets=validation_payload,
    )

    write_json(pack_root / "proposal.json", proposal)
    (pack_root / "README.md").write_text(
        _render_readme(
            campaign=campaign,
            proposal=proposal,
            best_comparator=best_comparator,
            evidence_payload=evidence_payload,
            validation_targets=validation_payload,
        ),
        encoding="utf-8",
    )
    (pack_root / "acceptance_criteria.md").write_text(_render_acceptance_criteria(proposal, target_files), encoding="utf-8")
    (pack_root / "target_files.txt").write_text("\n".join(target_files) + "\n", encoding="utf-8")
    (pack_root / "return_instructions.md").write_text(
        _render_return_instructions(campaign=campaign, proposal=proposal, validation_targets=validation_payload),
        encoding="utf-8",
    )

    write_json(context_root / "task_summary.json", task_summary)
    write_json(context_root / "evidence.json", evidence_payload)
    write_json(context_root / "validation_targets.json", validation_payload)
    (context_root / "local_contracts.md").write_text(
        _render_local_contracts(
            campaign=campaign,
            proposal=proposal,
            validation_targets=validation_payload,
        ),
        encoding="utf-8",
    )
    (context_root / "proposal_context.md").write_text(
        _render_proposal_context(
            campaign=campaign,
            proposal=proposal,
            best_comparator=best_comparator,
            parent_experiments=parent_experiments,
            evidence_payload=evidence_payload,
            validation_targets=validation_payload,
        ),
        encoding="utf-8",
    )
    copied_targets = _copy_target_files(paths.repo_root, files_root, target_files)

    return {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "pack_root": str(pack_root),
        "target_files": target_files,
        "evidence_count": len(evidence_payload.get("citations", [])),
        "warning_count": int(evidence_payload.get("warning_count") or 0),
        "validation_targets_path": str(context_root / "validation_targets.json"),
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
    proposal = normalize_proposal_payload(proposal)
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
    pack_root = paths.proposals_root / proposal["proposal_id"] / "code_pack"
    context_root = pack_root / "context"

    changed_files: list[str]
    deleted_files: list[str]
    return_kind: str
    source_path: Path
    patch_text: str
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
        patch_text = _build_patch_from_worktree(
            paths.repo_root,
            source_path,
            changed_files=changed_files,
            deleted_files=deleted_files,
        )
        patch_destination.write_text(patch_text, encoding="utf-8")
        return_kind = "worktree"

    if not changed_files and not deleted_files:
        raise CodeProposalImportError("returned code proposal did not contain any allowlisted changes")

    diff_stats = _patch_diff_stats(patch_text, changed_files=changed_files, deleted_files=deleted_files)
    evidence_path = context_root / "evidence.json"
    validation_targets_path = context_root / "validation_targets.json"
    proposal_context_path = context_root / "proposal_context.md"
    evidence_payload = _read_optional_json(evidence_path)
    validation_targets_payload = _read_optional_json(validation_targets_path)

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
        "diff_stats": diff_stats,
        "pack_root": _existing_path_str(pack_root),
        "evidence_path": _existing_path_str(evidence_path),
        "validation_targets_path": _existing_path_str(validation_targets_path),
        "proposal_context_path": _existing_path_str(proposal_context_path),
        "retrieval_event_id": proposal.get("retrieval_event_id"),
        "idea_signature": proposal.get("idea_signature"),
        "parent_ids": list(proposal.get("parent_ids", [])),
        "evidence_memory_ids": [str(item.get("memory_id")) for item in proposal.get("evidence", []) if str(item.get("memory_id") or "")],
        "validation_targets": validation_targets_payload,
        "generation_context": proposal.get("generation_context", {}),
        "evidence_summary": {
            "citation_count": len((evidence_payload or {}).get("citations", [])),
            "warning_count": int((evidence_payload or {}).get("warning_count") or 0),
        },
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
            "diff_stats": diff_stats,
            "evidence_path": return_manifest["evidence_path"],
            "validation_targets_path": return_manifest["validation_targets_path"],
            "proposal_context_path": return_manifest["proposal_context_path"],
            "evidence_memory_ids": return_manifest["evidence_memory_ids"],
            "validation_targets": validation_targets_payload,
        }
    )
    updated["code_patch"] = updated_code_patch
    updated["status"] = "queued"
    updated["generator"] = "imported"
    updated["notes"] = _append_note(
        updated.get("notes"),
        (
            f"Imported {return_kind} return at {imported_at}. "
            f"Touched {diff_stats['files_changed']} files (+{diff_stats['lines_added']}/-{diff_stats['lines_deleted']})."
        ),
    )

    payload = {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "import_root": str(import_root),
        "return_kind": return_kind,
        "patch_path": str(patch_destination),
        "changed_files": changed_files,
        "deleted_files": deleted_files,
        "diff_stats": diff_stats,
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


def stage_code_patch_artifacts(run_root: Path, return_manifest: dict[str, Any]) -> list[Path]:
    code_import_root = run_root / "code_import"
    code_import_root.mkdir(parents=True, exist_ok=True)
    staged_paths: list[Path] = []

    manifest_path = code_import_root / "return_manifest.json"
    write_json(manifest_path, return_manifest)
    staged_paths.append(manifest_path)

    artifact_map = {
        "patch_path": code_import_root / "returned.patch",
        "evidence_path": code_import_root / "evidence.json",
        "validation_targets_path": code_import_root / "validation_targets.json",
        "proposal_context_path": code_import_root / "proposal_context.md",
    }
    for key, destination in artifact_map.items():
        source_raw = return_manifest.get(key)
        if not source_raw:
            continue
        source = Path(str(source_raw))
        if not source.exists() or not source.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        staged_paths.append(destination)
    return staged_paths


def _build_evidence_payload(
    *,
    proposal: dict[str, Any],
    parent_experiments: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    retrieval_event: dict[str, Any] | None,
) -> dict[str, Any]:
    memory_by_id = {str(item.get("memory_id")): item for item in evidence_records}
    citations: list[dict[str, Any]] = []
    warning_count = 0
    for entry in proposal.get("evidence", []):
        memory_id = str(entry.get("memory_id") or "")
        record = memory_by_id.get(memory_id)
        citation_type = "warning" if str(entry.get("role") or "") == "warning" else "precedent"
        if citation_type == "warning":
            warning_count += 1
        citations.append(
            {
                "memory_id": memory_id,
                "record_type": str(entry.get("record_type") or (record or {}).get("record_type") or ""),
                "role": str(entry.get("role") or "supporting_precedent"),
                "citation_type": citation_type,
                "score": float(entry.get("score") or 0.0),
                "why_it_matters": str(entry.get("reason") or ""),
                "source_ref": str(entry.get("source_ref") or (record or {}).get("source_ref") or ""),
                "title": str((record or {}).get("title") or ""),
                "summary": str((record or {}).get("summary") or ""),
                "tags": list((record or {}).get("tags") or []),
                "payload": (record or {}).get("payload") or {},
            }
        )
    parent_validated_winners = [_parent_run_entry(item) for item in parent_experiments if is_validated_promotion(item)]
    parent_failures = [
        _parent_run_entry(item)
        for item in parent_experiments
        if str(item.get("status")) != "completed" or str(item.get("validation_state") or "") == "failed"
    ]
    return {
        "proposal_id": proposal["proposal_id"],
        "campaign_id": proposal["campaign_id"],
        "retrieval_event_id": proposal.get("retrieval_event_id"),
        "retrieval_query": {
            "query_text": retrieval_event.get("query_text"),
            "query_tags": retrieval_event.get("query_tags", []),
            "query_payload": retrieval_event.get("query_payload", {}),
        }
        if retrieval_event
        else None,
        "citation_count": len(citations),
        "warning_count": warning_count,
        "citations": citations,
        "parent_validated_winners": parent_validated_winners,
        "parent_failures": parent_failures,
    }


def _build_validation_targets(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    best_comparator: dict[str, Any] | None,
    parent_experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    comparator_ids: list[str] = []
    if best_comparator is not None:
        comparator_ids.append(str(best_comparator["experiment_id"]))
    for parent in parent_experiments:
        experiment_id = str(parent["experiment_id"])
        if experiment_id not in comparator_ids:
            comparator_ids.append(experiment_id)
    lane = str(proposal.get("lane") or "")
    return {
        "proposal_id": proposal["proposal_id"],
        "campaign_id": campaign["campaign_id"],
        "primary_metric": {
            "name": campaign["primary_metric"]["name"],
            "direction": campaign["primary_metric"]["direction"],
            "tie_threshold": campaign["primary_metric"].get("tie_threshold"),
        },
        "expected_direction": proposal.get("expected_direction"),
        "lane": lane,
        "confirm_review_required": lane == "confirm",
        "audit_expected": lane == "confirm",
        "audit_recommended": lane in {"main", "confirm"} or str(proposal.get("family") or "") in {"manual", "novel"},
        "comparator_experiment_ids": comparator_ids,
        "current_best_comparator_id": str(best_comparator["experiment_id"]) if best_comparator is not None else None,
        "current_best_comparator_metric": float(best_comparator["primary_metric_value"]) if best_comparator is not None else None,
    }


def _build_task_summary(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    best_comparator: dict[str, Any] | None,
    evidence_payload: dict[str, Any],
    validation_targets: dict[str, Any],
) -> dict[str, Any]:
    code_patch = proposal.get("code_patch", {})
    return {
        "proposal_id": proposal["proposal_id"],
        "campaign_id": campaign["campaign_id"],
        "lane": proposal["lane"],
        "family": proposal["family"],
        "kind": proposal["kind"],
        "hypothesis": proposal["hypothesis"],
        "rationale": proposal["rationale"],
        "target_files": list(code_patch.get("target_files", [])) if isinstance(code_patch, dict) else [],
        "acceptance_summary": str(code_patch.get("acceptance_summary") or "") if isinstance(code_patch, dict) else "",
        "primary_metric": {
            "name": campaign["primary_metric"]["name"],
            "direction": campaign["primary_metric"]["direction"],
        },
        "best_comparator": (
            {
                "experiment_id": str(best_comparator["experiment_id"]),
                "metric_name": str(best_comparator["primary_metric_name"]),
                "metric_value": float(best_comparator["primary_metric_value"]),
            }
            if best_comparator is not None
            else None
        ),
        "confirm_review_required": bool(validation_targets.get("confirm_review_required")),
        "audit_expected": bool(validation_targets.get("audit_expected")),
        "audit_recommended": bool(validation_targets.get("audit_recommended")),
        "retrieval_event_id": proposal.get("retrieval_event_id"),
        "evidence_count": int(evidence_payload.get("citation_count") or 0),
        "warning_count": int(evidence_payload.get("warning_count") or 0),
        "target_seam": ", ".join(list(code_patch.get("target_files", []))[:3]) if isinstance(code_patch, dict) else "",
    }


def _render_readme(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    best_comparator: dict[str, Any] | None,
    evidence_payload: dict[str, Any],
    validation_targets: dict[str, Any],
) -> str:
    comparator_line = "No current best comparator is recorded yet."
    if best_comparator is not None:
        comparator_line = (
            f"Current best comparator: {best_comparator['experiment_id']} "
            f"with {best_comparator['primary_metric_name']}={float(best_comparator['primary_metric_value']):.6f}."
        )
    prior_evidence = "No citations were attached to this proposal."
    if evidence_payload.get("citations"):
        highlights = [
            f"{item['memory_id']} ({item['citation_type']}): {item['why_it_matters'] or item['summary'] or 'context attached'}"
            for item in evidence_payload["citations"][:3]
        ]
        prior_evidence = "\n".join(f"- {item}" for item in highlights)
    return "\n".join(
        [
            f"# Code Proposal Pack: {proposal['proposal_id']}",
            "",
            "## What To Build",
            proposal["hypothesis"],
            "",
            "## Why Now",
            proposal["rationale"],
            "",
            "## Prior Evidence",
            prior_evidence,
            "",
            "## Allowed Files",
            *(f"- `{path}`" for path in proposal["code_patch"]["target_files"]),
            "",
            "## Success Judgment After Return",
            f"Primary metric: `{campaign['primary_metric']['name']}` ({campaign['primary_metric']['direction']}).",
            comparator_line,
            f"Confirm review required: {'yes' if validation_targets.get('confirm_review_required') else 'no'}.",
            f"Audit recommended: {'yes' if validation_targets.get('audit_recommended') else 'no'}.",
            "",
            "## Constraints",
            "- Stay within the target file allowlist in `target_files.txt`.",
            "- Keep the proposal aligned with the same runner and scoring pipeline.",
            "- Do not change campaign comparability semantics.",
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


def _render_return_instructions(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    validation_targets: dict[str, Any],
) -> str:
    comparator_ids = list(validation_targets.get("comparator_experiment_ids") or [])
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
            f"Expected direction: `{validation_targets.get('expected_direction') or proposal.get('expected_direction')}`",
            f"Confirm review required: {'yes' if validation_targets.get('confirm_review_required') else 'no'}",
            f"Audit expected: {'yes' if validation_targets.get('audit_expected') else 'no'}",
            f"Audit recommended: {'yes' if validation_targets.get('audit_recommended') else 'no'}",
            (
                "Comparator experiment IDs: " + ", ".join(comparator_ids)
                if comparator_ids
                else "Comparator experiment IDs: none recorded"
            ),
        ]
    )


def _render_local_contracts(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    validation_targets: dict[str, Any],
) -> str:
    target_files = list(proposal.get("code_patch", {}).get("target_files", []))
    return "\n".join(
        [
            "# Local Contracts",
            "",
            "## Runner Contract",
            "- The returned change must still execute through the normal `lab.cli run` path.",
            "- The target command must continue to emit a structured `summary.json` for scoring and reporting.",
            "- Do not introduce a second control plane or a custom one-off execution path.",
            "",
            "## Scientific Contract",
            f"- Campaign comparability stays anchored to `{campaign['campaign_id']}`.",
            f"- Primary metric remains `{campaign['primary_metric']['name']}` ({campaign['primary_metric']['direction']}).",
            "- Runtime tuning may change execution overlays, but it must not change scientific identity.",
            "",
            "## Validation Contract",
            f"- Expected direction: `{validation_targets.get('expected_direction') or proposal.get('expected_direction')}`.",
            f"- Confirm review required: {'yes' if validation_targets.get('confirm_review_required') else 'no'}.",
            f"- Audit recommended: {'yes' if validation_targets.get('audit_recommended') else 'no'}.",
            "",
            "## File Boundary",
            "- Stay inside the allowlist below unless a directly coupled test must move with it.",
            *(f"- `{path}`" for path in target_files),
        ]
    )


def _render_proposal_context(
    *,
    campaign: dict[str, Any],
    proposal: dict[str, Any],
    best_comparator: dict[str, Any] | None,
    parent_experiments: list[dict[str, Any]],
    evidence_payload: dict[str, Any],
    validation_targets: dict[str, Any],
) -> str:
    lines = [
        "# Proposal Context",
        "",
        f"Campaign: `{campaign['campaign_id']}`",
        f"Proposal: `{proposal['proposal_id']}`",
        f"Lane / family / kind: `{proposal['lane']}` / `{proposal['family']}` / `{proposal['kind']}`",
        f"Idea signature: `{proposal.get('idea_signature')}`",
        f"Target files: {', '.join(proposal.get('code_patch', {}).get('target_files', [])) or 'none'}",
        "",
        "## Hypothesis",
        proposal["hypothesis"],
        "",
        "## Rationale",
        proposal["rationale"],
        "",
        "## Generation Context",
        f"- Family selector reason: {proposal.get('generation_context', {}).get('family_selector_reason') or 'n/a'}",
        f"- Anchor experiment IDs: {', '.join(proposal.get('generation_context', {}).get('anchor_experiment_ids', [])) or 'none'}",
        f"- Blocked idea signatures: {', '.join(proposal.get('generation_context', {}).get('blocked_idea_signatures', [])) or 'none'}",
        f"- Retrieval event ID: {proposal.get('retrieval_event_id') or 'none'}",
        "",
        "## Comparator State",
    ]
    if best_comparator is None:
        lines.append("- No comparator experiment is currently recorded.")
    else:
        lines.extend(
            [
                f"- Best comparator experiment: `{best_comparator['experiment_id']}`",
                (
                    f"- Comparator metric: `{best_comparator['primary_metric_name']}`="
                    f"{float(best_comparator['primary_metric_value']):.6f}"
                ),
            ]
        )
    lines.extend(["", "## Parent Runs"])
    if not parent_experiments:
        lines.append("- No explicit parent runs are attached.")
    else:
        for item in parent_experiments:
            lines.append(
                "- "
                + f"`{item['experiment_id']}` {item.get('disposition') or item.get('status') or 'unknown'} "
                + f"{item.get('primary_metric_name') or campaign['primary_metric']['name']}="
                + (
                    "n/a"
                    if item.get("primary_metric_value") is None
                    else f"{float(item['primary_metric_value']):.6f}"
                )
            )
    lines.extend(["", "## Evidence"])
    if not evidence_payload.get("citations"):
        lines.append("- No memory citations are attached.")
    else:
        for item in evidence_payload["citations"]:
            lines.append(
                "- "
                + f"`{item['memory_id']}` [{item['citation_type']}] "
                + (item["why_it_matters"] or item["summary"] or item["title"] or "context attached")
            )
    lines.extend(
        [
            "",
            "## Validation Intent",
            (
                f"- Primary metric: `{validation_targets['primary_metric']['name']}` "
                f"({validation_targets['primary_metric']['direction']})"
            ),
            f"- Expected direction: {validation_targets.get('expected_direction') or proposal.get('expected_direction')}",
            f"- Confirm review required: {'yes' if validation_targets.get('confirm_review_required') else 'no'}",
            f"- Audit expected: {'yes' if validation_targets.get('audit_expected') else 'no'}",
            f"- Audit recommended: {'yes' if validation_targets.get('audit_recommended') else 'no'}",
            (
                "- Comparator experiment IDs: " + ", ".join(validation_targets.get("comparator_experiment_ids", []))
                if validation_targets.get("comparator_experiment_ids")
                else "- Comparator experiment IDs: none recorded"
            ),
        ]
    )
    return "\n".join(lines)


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


def _parent_run_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": str(row.get("experiment_id") or ""),
        "lane": row.get("lane"),
        "status": row.get("status"),
        "disposition": row.get("disposition"),
        "validation_state": row.get("validation_state"),
        "primary_metric_name": row.get("primary_metric_name"),
        "primary_metric_value": row.get("primary_metric_value"),
    }


def _patch_diff_stats(patch_text: str, *, changed_files: list[str], deleted_files: list[str]) -> dict[str, int]:
    lines_added = 0
    lines_deleted = 0
    for line in patch_text.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+"):
            lines_added += 1
        elif line.startswith("-"):
            lines_deleted += 1
    return {
        "files_changed": len(changed_files),
        "files_deleted": len(deleted_files),
        "lines_added": lines_added,
        "lines_deleted": lines_deleted,
    }


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _existing_path_str(path: Path) -> str | None:
    return str(path) if path.exists() else None


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
    "stage_code_patch_artifacts",
]
