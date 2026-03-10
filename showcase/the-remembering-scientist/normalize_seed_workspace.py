from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: normalize_seed_workspace.py <db_path> <proposals_dir>")

    db_path = Path(sys.argv[1]).resolve()
    proposals_dir = Path(sys.argv[2]).resolve()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT proposal_id, proposal_json FROM proposals WHERE status IN ('queued', 'running')"
    ).fetchall()

    superseded: list[str] = []
    for row in rows:
        proposal_id = str(row["proposal_id"])
        proposal_json = row["proposal_json"]
        payload = json.loads(proposal_json) if proposal_json else {}
        if isinstance(payload, dict):
            payload["status"] = "superseded"
            encoded = json.dumps(payload, sort_keys=True)
        else:
            encoded = proposal_json
        connection.execute(
            "UPDATE proposals SET status = 'superseded', proposal_json = ?, updated_at = datetime('now') WHERE proposal_id = ?",
            (encoded, proposal_id),
        )
        proposal_path = proposals_dir / f"{proposal_id}.json"
        if proposal_path.exists():
            file_payload = json.loads(proposal_path.read_text(encoding="utf-8"))
            if isinstance(file_payload, dict):
                file_payload["status"] = "superseded"
                proposal_path.write_text(json.dumps(file_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        superseded.append(proposal_id)

    connection.commit()
    connection.close()
    print(json.dumps({"superseded": superseded}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
