from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["import_error", "oom_train", "oom_eval", "assertion", "timeout"], required=True)
    args = parser.parse_args()

    time.sleep(0.02)

    if args.kind == "import_error":
        print("ModuleNotFoundError: No module named 'imaginary_backend'", file=sys.stderr)
        return 2
    if args.kind == "oom_train":
        print("RuntimeError: CUDA out of memory", file=sys.stderr)
        return 3
    if args.kind == "oom_eval":
        print("RuntimeError: CUDA out of memory during eval", file=sys.stderr)
        return 4
    if args.kind == "assertion":
        print("AssertionError: metric must be finite", file=sys.stderr)
        return 5
    if args.kind == "timeout":
        print("timed out waiting for target to finish", file=sys.stderr)
        return 6
    return 99


if __name__ == "__main__":
    raise SystemExit(main())
