"""Compare two completed feedback-diagnostic summary files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["rule_variant"]: row for row in csv.DictReader(handle)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    args = parser.parse_args()
    first, second = _read(args.first), _read(args.second)
    print(
        json.dumps(
            {
                "first": str(args.first.resolve()),
                "second": str(args.second.resolve()),
                "identical": first == second,
                "first_variants": sorted(first),
                "second_variants": sorted(second),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
