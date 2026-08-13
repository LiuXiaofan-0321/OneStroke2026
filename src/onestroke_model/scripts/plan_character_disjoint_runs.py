"""Write a frozen character-disjoint training/evaluation execution plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.character_disjoint_runs import build_character_disjoint_run_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan character-disjoint model runs.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--split-report",
        default=(
            "artifacts/paper_ijdar/character_disjoint/"
            "character_disjoint_split_report.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "artifacts/paper_ijdar/character_disjoint/"
            "character_disjoint_execution_plan.json"
        ),
    )
    args = parser.parse_args()
    plan = build_character_disjoint_run_plan(
        args.project_root,
        split_report_path=args.split_report,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
