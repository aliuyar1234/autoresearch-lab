from __future__ import annotations

import json
from hashlib import sha1
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def memory_id_for(*, record_type: str, source_kind: str, source_ref: str, payload_core: dict[str, Any]) -> str:
    digest = sha1(
        canonical_json(
            {
                "record_type": record_type,
                "source_kind": source_kind,
                "source_ref": source_ref,
                "payload_core": payload_core,
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"mem_{digest[:16]}"


def retrieval_event_id_for(proposal_id: str) -> str:
    digest = sha1(proposal_id.encode("utf-8")).hexdigest()
    return f"ret_{digest[:16]}"
