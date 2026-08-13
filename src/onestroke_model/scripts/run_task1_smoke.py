"""Plan or execute a one-batch GPU smoke test for all three Task 1 models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.task1_smoke import run_task1_smoke


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_task1_smoke(args.project_root, execute=args.execute),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
