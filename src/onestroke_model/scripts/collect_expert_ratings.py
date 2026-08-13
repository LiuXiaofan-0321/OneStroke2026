"""Validate and merge completed evaluator CSV exports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate one rating export per evaluator and merge them."
    )
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--ratings", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    pair_rows = _read(Path(args.pairs))
    valid_blinded_ids = {row["blinded_pair_id"] for row in pair_rows}
    expected = len(valid_blinded_ids)
    merged: list[dict[str, Any]] = []
    evaluator_ids: set[str] = set()
    report: dict[str, Any] = {"expected_presentations": expected, "files": []}
    for value in args.ratings:
        path = Path(value)
        rows = _read(path)
        evaluator_values = {
            row.get("evaluator_id", "").strip()
            for row in rows
            if row.get("evaluator_id", "").strip()
        }
        if len(evaluator_values) != 1:
            raise SystemExit(f"{path}: expected one evaluator_id, got {evaluator_values}")
        evaluator_id = next(iter(evaluator_values))
        if evaluator_id in evaluator_ids:
            raise SystemExit(f"duplicate evaluator export: {evaluator_id}")
        evaluator_ids.add(evaluator_id)
        seen: set[str] = set()
        missing_ratings = 0
        for row in rows:
            blinded_id = row.get("blinded_pair_id", "").strip()
            if blinded_id not in valid_blinded_ids:
                raise SystemExit(f"{path}: unknown blinded_pair_id {blinded_id!r}")
            if blinded_id in seen:
                raise SystemExit(f"{path}: duplicate row for {blinded_id}")
            seen.add(blinded_id)
            rating = row.get("structural_similarity_rating_1_to_5", "").strip()
            if rating == "":
                missing_ratings += 1
            else:
                numeric = float(rating)
                if numeric not in {1, 2, 3, 4, 5}:
                    raise SystemExit(f"{path}: invalid rating {rating!r}")
            merged.append(
                {
                    "blinded_pair_id": blinded_id,
                    "evaluator_id": evaluator_id,
                    "rating": rating,
                    "optional_comment": row.get("optional_comment", ""),
                }
            )
        missing_ids = sorted(valid_blinded_ids - seen)
        report["files"].append(
            {
                "path": str(path.resolve()),
                "evaluator_id": evaluator_id,
                "row_count": len(rows),
                "missing_pair_ids": missing_ids,
                "missing_rating_count": missing_ratings,
            }
        )
        if len(rows) != expected or missing_ids or missing_ratings:
            raise SystemExit(
                f"{path}: incomplete export; rows={len(rows)}/{expected}, "
                f"missing_ids={len(missing_ids)}, missing_ratings={missing_ratings}"
            )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "blinded_pair_id",
                "evaluator_id",
                "rating",
                "optional_comment",
            ),
        )
        writer.writeheader()
        writer.writerows(merged)
    report["evaluator_ids"] = sorted(evaluator_ids)
    report["merged_rating_count"] = len(merged)
    report["output"] = str(output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
