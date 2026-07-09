from __future__ import annotations

import argparse

from onestroke_model.data.split import assign_splits
from onestroke_model.utils.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed train/val/test splits from manifest.csv.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/data_audit/splits.csv")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args()

    report = assign_splits(args.manifest, args.output, args.train_ratio, args.val_ratio)
    write_json(str(args.output).replace(".csv", "_report.json"), report)
    print(report)


if __name__ == "__main__":
    main()

