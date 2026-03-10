from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Any

from .ledger.db import connect
from .ledger.queries import get_experiment, get_proposal
from .paths import LabPaths
from .proposals import normalize_proposal_payload
from .utils import read_json, utc_now_iso, validate_payload, load_schema


def load_replay_proposal(
    paths: LabPaths,
    *,
    experiment_id: str | None = None,
    proposal_id: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    if bool(experiment_id) == bool(proposal_id):
        raise ValueError("replay requires exactly one of --experiment or --proposal")

    if experiment_id:
        source_proposal = _load_proposal_from_experiment(paths, experiment_id)
        cloned = clone_proposal_for_replay(source_proposal, source_experiment_id=experiment_id)
        return cloned, experiment_id

    assert proposal_id is not None
    connection = connect(paths.db_path)
    try:
        row = get_proposal(connection, proposal_id)
    finally:
        connection.close()
    if not row:
        raise FileNotFoundError(f"proposal not found: {proposal_id}")
    payload = read_json_payload(row["proposal_json"])
    cloned = clone_proposal_for_replay(payload, source_experiment_id=None)
    return cloned, None


def clone_proposal_for_replay(proposal: dict[str, Any], *, source_experiment_id: str | None) -> dict[str, Any]:
    cloned = normalize_proposal_payload(copy.deepcopy(proposal))
    cloned["proposal_id"] = _allocate_replay_proposal_id(str(proposal["proposal_id"]))
    cloned["status"] = "queued"
    cloned["generator"] = "replay"
    cloned["created_at"] = utc_now_iso()
    if source_experiment_id:
        parent_ids = [source_experiment_id, *proposal.get("parent_ids", [])]
        cloned["parent_ids"] = list(dict.fromkeys(parent_ids))
    else:
        cloned["parent_ids"] = list(proposal.get("parent_ids", []))
    note_prefix = f"Replay of experiment {source_experiment_id}" if source_experiment_id else "Replay of proposal"
    prior_notes = proposal.get("notes")
    cloned["notes"] = note_prefix if not prior_notes else f"{prior_notes}\n{note_prefix}"
    return normalize_proposal_payload(cloned)


def _load_proposal_from_experiment(paths: LabPaths, experiment_id: str) -> dict[str, Any]:
    connection = connect(paths.db_path)
    try:
        row = get_experiment(connection, experiment_id)
        if not row:
            raise FileNotFoundError(f"experiment not found: {experiment_id}")
        proposal_id = row.get("proposal_id")
        if proposal_id:
            proposal_row = get_proposal(connection, proposal_id)
            if proposal_row:
                return read_json_payload(proposal_row["proposal_json"])
    finally:
        connection.close()

    proposal_path = Path(row["artifact_root"]) / "proposal.json"
    if not proposal_path.exists():
        raise FileNotFoundError(f"proposal snapshot not found for experiment: {experiment_id}")
    payload = read_json(proposal_path)
    validate_payload(payload, load_schema(paths.schemas_root / "proposal.schema.json"))
    return payload


def _allocate_replay_proposal_id(base_proposal_id: str) -> str:
    return f"{base_proposal_id}_replay_{uuid.uuid4().hex[:8]}"


def read_json_payload(raw_json: str) -> dict[str, Any]:
    payload = read_json_string(raw_json)
    if not isinstance(payload, dict):
        raise ValueError("proposal payload must be a JSON object")
    return payload


def read_json_string(raw_json: str) -> Any:
    import json

    return json.loads(raw_json)
