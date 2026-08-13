"""Build strict IJDAR tables, inventories, and readiness status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.paper_results import build_ijdar_paper_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate only frozen formal artifacts into IJDAR paper outputs."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = build_ijdar_paper_results(args.project_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
