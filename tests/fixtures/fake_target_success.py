from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--eval-split", default="search_val")
    parser.add_argument("--run-purpose", default="search")
    parser.add_argument("--metric", type=float, default=0.97)
    parser.add_argument("--backend", default="test_backend")
    parser.add_argument("--device-profile", default="test_profile")
    parser.add_argument("--write-checkpoint", action="store_true")
    parser.add_argument("--fail-after-checkpoint", action="store_true")
    args = parser.parse_args()

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    time.sleep(0.05)

    checkpoint_path = os.environ.get("LAB_PRE_EVAL_CHECKPOINT_PATH")
    checkpoint_meta_path = os.environ.get("LAB_PRE_EVAL_META_PATH")
    if args.write_checkpoint and checkpoint_path and checkpoint_meta_path:
        checkpoint_file = Path(checkpoint_path)
        checkpoint_meta_file = Path(checkpoint_meta_path)
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_bytes(b"fake checkpoint bytes\n")
        checkpoint_meta_file.write_text(
            json.dumps(
                {
                    "experiment_id": args.experiment_id,
                    "proposal_id": args.proposal_id,
                    "lane": args.lane,
                    "created_by": "fake_target_success",
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        if args.fail_after_checkpoint:
            print("final eval crashed after checkpoint", flush=True)
            return 7

    payload = {
        "experiment_id": args.experiment_id,
        "proposal_id": args.proposal_id,
        "campaign_id": args.campaign_id,
        "lane": args.lane,
        "status": "completed",
        "eval_split": args.eval_split,
        "run_purpose": args.run_purpose,
        "validation_state": "not_required",
        "validation_review_id": os.environ.get("LAB_VALIDATION_REVIEW_ID"),
        "replay_source_experiment_id": os.environ.get("LAB_REPLAY_SOURCE_EXPERIMENT_ID"),
        "primary_metric_name": "val_bpb",
        "primary_metric_value": args.metric,
        "budget_seconds": 1,
        "train_seconds": 0.5,
        "eval_seconds": 0.1,
        "tokens_processed": 2048,
        "tokens_per_second": 4096.0,
        "peak_vram_gb": 1.0,
        "backend": args.backend,
        "device_profile": args.device_profile,
        "seed": 42,
        "config_fingerprint": "abc123deadbeef",
        "git_commit": "deadbeef",
        "warnings": [],
        "checkpoint_path": checkpoint_path if args.write_checkpoint else None,
        "summary_version": "1.1.0",
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print("fake success target completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
