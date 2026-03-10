from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _shared import SHOWCASE_ROOT, materialize_snapshot, snapshot_counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze a showcase-specific historical memory snapshot.")
    parser.add_argument("--campaign", action="append", dest="campaigns", required=True, help="campaign id to preserve")
    parser.add_argument("--source-db", type=Path, required=True, help="source lab SQLite database")
    parser.add_argument("--output-root", type=Path, default=SHOWCASE_ROOT / "01_seed_snapshot")
    parser.add_argument("--include-source-kind", action="append", default=[])
    parser.add_argument("--exclude-source-kind", action="append", default=[])
    parser.add_argument("--copy-artifacts", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = materialize_snapshot(
        source_db=args.source_db.resolve(),
        output_root=args.output_root.resolve(),
        campaign_ids=[str(item) for item in args.campaigns],
        include_source_kinds=[str(item) for item in args.include_source_kind],
        exclude_source_kinds=[str(item) for item in args.exclude_source_kind],
        copy_artifacts=bool(args.copy_artifacts),
    )
    manifest["counts"] = snapshot_counts(Path(manifest["snapshot_db_path"]))
    print(
        json.dumps(
            {
                "ok": True,
                "output_root": str(args.output_root.resolve()),
                "manifest_path": str((args.output_root.resolve() / "MANIFEST.json")),
                "snapshot_hash": manifest["snapshot_hash"],
                "counts": manifest["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
