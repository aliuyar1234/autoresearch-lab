from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROUNDTRIP_MARKER = "# code-patch roundtrip marker"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--backend", default="test_backend")
    parser.add_argument("--device-profile", default="test_profile")
    args = parser.parse_args()

    execution_root = Path(os.environ.get("LAB_EXECUTION_REPO_ROOT") or Path.cwd())
    train_path = execution_root / "train.py"
    if not train_path.exists():
        print("AssertionError: execution snapshot is missing train.py", flush=True)
        return 7
    train_text = train_path.read_text(encoding="utf-8")
    if ROUNDTRIP_MARKER not in train_text:
        print("AssertionError: imported code patch marker not found in execution snapshot", flush=True)
        return 8

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": args.experiment_id,
        "proposal_id": args.proposal_id,
        "campaign_id": args.campaign_id,
        "lane": args.lane,
        "status": "completed",
        "primary_metric_name": "val_bpb",
        "primary_metric_value": 0.955,
        "budget_seconds": 1,
        "train_seconds": 0.2,
        "eval_seconds": 0.05,
        "compile_seconds": 0.01,
        "tokens_processed": 1024,
        "tokens_per_second": 5120.0,
        "steady_state_mfu": 0.01,
        "peak_vram_gb": 1.5,
        "param_count": 123456,
        "backend": args.backend,
        "device_profile": args.device_profile,
        "seed": 42,
        "config_fingerprint": "codepatchfixture",
        "git_commit": "codepatchfixture",
        "warnings": [],
        "checkpoint_path": None,
        "summary_version": "1.0.0",
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
