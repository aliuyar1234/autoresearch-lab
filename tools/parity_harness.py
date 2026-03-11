from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _extract_int_constant(source: str, name: str) -> int | None:
    match = re.search(rf"^{re.escape(name)}\s*=\s*([0-9\*\s\(\)]+)", source, re.MULTILINE)
    if not match:
        return None
    expression = match.group(1).strip()
    try:
        node = ast.parse(expression, mode="eval")
        if not all(isinstance(item, (ast.Expression, ast.BinOp, ast.Mult, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub)) for item in ast.walk(node)):
            return None
        return int(eval(compile(node, "<parity-const>", "eval"), {"__builtins__": {}}, {}))
    except Exception:
        return None


def _extract_argument_default(source: str, flag: str) -> str | None:
    pattern = re.compile(rf'add_argument\("{re.escape(flag)}"[^)]*default=([^,\)]+)', re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return None
    return match.group(1).strip()


def _status(*, aligned: bool) -> str:
    return "aligned" if aligned else "documented_difference"


def build_static_parity_report(*, repo_root: Path, campaign_id: str = "base_2k") -> dict[str, Any]:
    campaign_path = repo_root / "campaigns" / campaign_id / "campaign.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))

    prepare_source = (repo_root / "prepare.py").read_text(encoding="utf-8")
    upstream_train_source = (repo_root / "train.py").read_text(encoding="utf-8")
    lab_train_source = (repo_root / "research" / "dense_gpt" / "train.py").read_text(encoding="utf-8")

    upstream_max_seq_len = _extract_int_constant(prepare_source, "MAX_SEQ_LEN")
    upstream_time_budget = _extract_int_constant(prepare_source, "TIME_BUDGET")
    upstream_eval_tokens = _extract_int_constant(prepare_source, "EVAL_TOKENS")
    upstream_vocab_size = _extract_int_constant(prepare_source, "VOCAB_SIZE")
    lab_eval_batches = _extract_argument_default(lab_train_source, "--eval-batches")

    checks = [
        {
            "name": "sequence_length",
            "status": _status(aligned=campaign["sequence_length"] == upstream_max_seq_len),
            "campaign_value": campaign["sequence_length"],
            "upstream_value": upstream_max_seq_len,
            "details": "The canonical campaign should preserve the upstream 2048-context shape.",
        },
        {
            "name": "fixed_budget",
            "status": _status(aligned=int(campaign["budgets"]["main_seconds"]) == upstream_time_budget),
            "campaign_value": int(campaign["budgets"]["main_seconds"]),
            "upstream_value": upstream_time_budget,
            "details": "The canonical campaign should preserve the upstream 300-second main run budget.",
        },
        {
            "name": "vocab_size_target",
            "status": _status(aligned=int(campaign["vocab_size"]) == int(upstream_vocab_size or 0)),
            "campaign_value": int(campaign["vocab_size"]),
            "upstream_value": upstream_vocab_size,
            "details": "The canonical campaign should preserve the upstream 8192-vocab target.",
        },
        {
            "name": "primary_metric",
            "status": _status(aligned=str(campaign["primary_metric"]["name"]) == "val_bpb"),
            "campaign_value": str(campaign["primary_metric"]["name"]),
            "upstream_value": "val_bpb",
            "details": "Parity is about val_bpb semantics, not exact floating point identity.",
        },
        {
            "name": "dataset_contract",
            "status": "documented_difference",
            "campaign_value": {
                "source": campaign["dataset"]["source"],
                "format": campaign["dataset"]["format"],
                "builder_contract": campaign["dataset"].get("builder_contract"),
            },
            "upstream_value": {
                "source": "karpathy/climbmix-400b-shuffle",
                "format": "parquet",
                "download_path": "~/.cache/autoresearch/data",
            },
            "details": "The lab canonical campaign uses local UTF-8 text shards named like upstream shards; upstream prepare.py downloads and reads parquet directly.",
        },
        {
            "name": "tokenizer_contract",
            "status": "documented_difference",
            "campaign_value": {
                "kind": campaign["tokenizer"]["kind"],
                "vocab_size": campaign["tokenizer"]["vocab_size"],
            },
            "upstream_value": {
                "kind": "rustbpe_bpe",
                "vocab_size": upstream_vocab_size,
            },
            "details": "The lab campaign builder emits deterministic byte-fallback assets. Upstream prepare.py trains a rustbpe BPE tokenizer.",
        },
        {
            "name": "evaluation_semantics",
            "status": "documented_difference",
            "campaign_value": {
                "lab_eval_batches_default": lab_eval_batches,
                "explicit_splits": ["search_val", "audit_val", "locked_val"],
            },
            "upstream_value": {
                "fixed_eval_tokens": upstream_eval_tokens,
                "split": "val",
            },
            "details": "The lab path makes eval split explicit but uses bounded eval batches by default; upstream uses a fixed EVAL_TOKENS window on the pinned validation shard.",
        },
        {
            "name": "trainer_mechanics",
            "status": "documented_difference",
            "campaign_value": {
                "path": "research/dense_gpt/train.py",
                "compile_capable": "--backend" in lab_train_source,
                "data_mode": "campaign_assets",
            },
            "upstream_value": {
                "path": "train.py",
                "has_muon_adamw": "MuonAdamW" in upstream_train_source,
                "has_value_embeddings": "value_embeds" in upstream_train_source,
                "has_x0_scaling": "x0_lambdas" in upstream_train_source,
            },
            "details": "The lab-native trainer is the structured-search engine. The upstream trainer remains the baseline truth anchor for direct scientific-mechanics parity.",
        },
    ]

    return {
        "ok": True,
        "repo_root": str(repo_root),
        "campaign_id": campaign_id,
        "campaign_path": str(campaign_path),
        "checks": checks,
        "baseline_role": {
            "prepare_py": "truth anchor for data/tokenizer/budget semantics",
            "train_py": "truth anchor for the upstream direct training loop",
            "lab_native_train_py": "primary structured-search engine for normal lab runs",
        },
        "recommended_use": {
            "canonical_lab_run": "uv run arlab night --campaign base_2k --hours 8 --allow-confirm",
            "showcase_run": "python showcase/the-remembering-scientist/run_ab_test.py --campaign base_2k --output-root showcase/the-remembering-scientist --snapshot-root showcase/the-remembering-scientist/01_seed_snapshot --pairs 1 --hours 4 --max-runs 12 --allow-confirm",
        },
    }


def compare_summary_files(*, upstream_summary_path: Path, lab_summary_path: Path) -> dict[str, Any]:
    upstream_summary = json.loads(upstream_summary_path.read_text(encoding="utf-8"))
    lab_summary = json.loads(lab_summary_path.read_text(encoding="utf-8"))

    upstream_metric_name = str(upstream_summary.get("primary_metric_name") or upstream_summary.get("metric_name") or "val_bpb")
    lab_metric_name = str(lab_summary.get("primary_metric_name") or lab_summary.get("metric_name") or "")
    upstream_budget = upstream_summary.get("budget_seconds") or upstream_summary.get("time_budget_seconds")
    lab_budget = lab_summary.get("budget_seconds") or lab_summary.get("time_budget_seconds")

    return {
        "metric_name_alignment": upstream_metric_name == lab_metric_name,
        "budget_alignment": upstream_budget == lab_budget,
        "upstream": {
            "path": str(upstream_summary_path),
            "metric_name": upstream_metric_name,
            "metric_value": upstream_summary.get("primary_metric_value") or upstream_summary.get("val_bpb"),
            "budget_seconds": upstream_budget,
            "eval_split": upstream_summary.get("eval_split", "val"),
        },
        "lab": {
            "path": str(lab_summary_path),
            "metric_name": lab_metric_name,
            "metric_value": lab_summary.get("primary_metric_value") or lab_summary.get("val_bpb"),
            "budget_seconds": lab_budget,
            "eval_split": lab_summary.get("eval_split"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report the current upstream-vs-lab parity contract.")
    parser.add_argument("--campaign", default="base_2k", help="campaign id to inspect (default: base_2k)")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="repo root to inspect")
    parser.add_argument("--upstream-summary", type=Path, help="optional upstream summary json to compare")
    parser.add_argument("--lab-summary", type=Path, help="optional lab summary json to compare")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_static_parity_report(repo_root=args.repo_root.resolve(), campaign_id=args.campaign)
    if args.upstream_summary or args.lab_summary:
        if not args.upstream_summary or not args.lab_summary:
            raise SystemExit("both --upstream-summary and --lab-summary are required together")
        payload["summary_comparison"] = compare_summary_files(
            upstream_summary_path=args.upstream_summary.resolve(),
            lab_summary_path=args.lab_summary.resolve(),
        )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Parity harness")
        print(f"campaign: {payload['campaign_id']}")
        for check in payload["checks"]:
            print(f"- {check['name']}: {check['status']}")
            print(f"  {check['details']}")
        if "summary_comparison" in payload:
            comparison = payload["summary_comparison"]
            print("- summary comparison:")
            print(f"  metric_name_alignment: {comparison['metric_name_alignment']}")
            print(f"  budget_alignment: {comparison['budget_alignment']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
