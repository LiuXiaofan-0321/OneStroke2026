"""Preflight or execute the complete resumable 18-run Task 1 benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.task1_benchmark import run_task1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Train, calibrate on validation, and evaluate all incomplete runs.",
    )
    args = parser.parse_args()
    result = run_task1(args.project_root, execute=args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
