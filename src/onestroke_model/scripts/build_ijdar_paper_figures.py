"""Generate IJDAR figures from completed formal artifact tables."""

from __future__ import annotations

import argparse
import json

from onestroke_model.paper_figures import build_formal_figures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper-root",
        default="artifacts/paper_ijdar",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/final_figures",
    )
    args = parser.parse_args()
    report = build_formal_figures(args.paper_root, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
