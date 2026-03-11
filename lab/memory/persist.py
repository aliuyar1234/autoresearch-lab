from __future__ import annotations

from typing import Any

from ..ledger.queries import replace_proposal_evidence_links, replace_retrieval_event_items, upsert_retrieval_event
from ..utils import load_schema, validate_payload


def _existing_memory_ids(connection, memory_ids: list[str]) -> set[str]:
    ids = sorted({str(item) for item in memory_ids if str(item)})
    if not ids:
        return set()
    placeholders = ", ".join("?" for _ in ids)
    rows = connection.execute(
        f"SELECT memory_id FROM memory_records WHERE memory_id IN ({placeholders})",
        ids,
    ).fetchall()
    return {str(row["memory_id"]) for row in rows}


def persist_proposal_memory_state(connection, *, paths, proposal: dict[str, Any]) -> None:
    retrieval_event_id = proposal.get("retrieval_event_id")
    retrieval_event = proposal.get("retrieval_event")
    if not isinstance(retrieval_event, dict):
        retrieval_event = proposal.get("_retrieval_event")
    persisted_retrieval_event_id: str | None = None
    evidence = list(proposal.get("evidence", []))
    memory_ids = [str(item.get("memory_id") or "") for item in evidence]
    if isinstance(retrieval_event, dict):
        memory_ids.extend(str(item.get("memory_id") or "") for item in retrieval_event.get("items", []))
    existing_memory_ids = _existing_memory_ids(connection, memory_ids)
    if retrieval_event_id and isinstance(retrieval_event, dict):
        persisted_event = {
            "retrieval_event_id": retrieval_event["retrieval_event_id"],
            "campaign_id": retrieval_event["campaign_id"],
            "proposal_id": retrieval_event.get("proposal_id"),
            "family": retrieval_event.get("family"),
            "lane": retrieval_event.get("lane"),
            "query_text": retrieval_event["query_text"],
            "query_tags": list(retrieval_event.get("query_tags", [])),
            "query_payload": dict(retrieval_event.get("query_payload", {})),
            "items": [
                item
                for item in list(retrieval_event.get("items", []))
                if str(item.get("memory_id") or "") in existing_memory_ids
            ],
            "created_at": retrieval_event["created_at"],
        }
        validate_payload(persisted_event, load_schema(paths.schemas_root / "retrieval_event.schema.json"))
        upsert_retrieval_event(connection, persisted_event)
        replace_retrieval_event_items(
            connection,
            retrieval_event_id=str(retrieval_event_id),
            items=list(persisted_event.get("items", [])),
            created_at=str(persisted_event["created_at"]),
        )
        persisted_retrieval_event_id = str(retrieval_event_id)
    elif retrieval_event_id:
        row = connection.execute(
            "SELECT 1 FROM retrieval_events WHERE retrieval_event_id = ?",
            (str(retrieval_event_id),),
        ).fetchone()
        if row is not None:
            persisted_retrieval_event_id = str(retrieval_event_id)
    replace_proposal_evidence_links(
        connection,
        proposal_id=str(proposal["proposal_id"]),
        retrieval_event_id=persisted_retrieval_event_id,
        evidence=[
            item
            for item in evidence
            if str(item.get("memory_id") or "") in existing_memory_ids
        ],
        created_at=str(
            (retrieval_event or {}).get("created_at")
            or proposal.get("updated_at")
            or proposal.get("created_at")
        ),
    )
