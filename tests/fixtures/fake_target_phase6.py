from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


_METRICS = {
    "baseline": 1.020000,
    "exploit": 0.960000,
    "ablation": 1.005000,
    "combine": 0.945000,
    "novel": 0.985000,
    "manual": 0.990000,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--eval-split", default="search_val")
    parser.add_argument("--run-purpose", default="search")
    parser.add_argument("--backend", default="test_backend")
    parser.add_argument("--device-profile", default="test_profile")
    args = parser.parse_args()

    proposal = _load_proposal()
    family = str(proposal.get("family") or "manual")
    if family == "novel":
        print("RuntimeError: CUDA out of memory during eval", flush=True)
        return 4

    metric = _METRICS.get(family, 0.990000)
    if str(args.lane) == "confirm":
        metric -= 0.010000

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
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
        "primary_metric_value": metric,
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
        "config_fingerprint": str(proposal.get("config_fingerprint") or "phase6fixture"),
        "git_commit": "phase6fixture",
        "warnings": [],
        "checkpoint_path": None,
        "summary_version": "1.1.0",
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _load_proposal() -> dict[str, object]:
    artifact_root = os.environ.get("LAB_ARTIFACT_ROOT")
    if artifact_root:
        proposal_path = Path(artifact_root) / "proposal.json"
        if proposal_path.exists():
            return json.loads(proposal_path.read_text(encoding="utf-8"))
    return {}


if __name__ == "__main__":
    raise SystemExit(main())
