"""Merge a manually reviewed hard-set CSV into the canonical UTF-8 review file."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from onestroke_model.scripts.prepare_hardset_review import REVIEW_FIELDS
from onestroke_model.utils.io import write_csv_rows


ANNOTATION_FIELDS = [
    "difficulty_crossing",
    "difficulty_adhesion",
    "difficulty_endpoint",
    "difficulty_line_width",
    "difficulty_background",
    "difficulty_style",
    "priority",
    "reviewer",
    "keep",
    "notes",
]
MANUAL_SIGNAL_FIELDS = [
    "difficulty_crossing",
    "difficulty_adhesion",
    "difficulty_endpoint",
    "difficulty_line_width",
    "difficulty_background",
    "difficulty_style",
    "reviewer",
    "keep",
]


def _read_csv_with_fallback(path: str | Path) -> list[dict[str, str]]:
    """Accept common spreadsheet exports while keeping canonical output UTF-8."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return list(csv.DictReader(raw.decode(encoding).splitlines()))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode {path}; save it as UTF-8 or GB18030 CSV")


def _row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("char_id", "").strip(), row.get("sample_index", "").strip()


def _canonical_sample_id(row: dict[str, str]) -> str:
    sample_id = row.get("sample_id", "").strip()
    if re.fullmatch(r"\d+/\d+", sample_id):
        return sample_id
    char_id, sample_index = _row_key(row)
    if char_id.isdigit() and sample_index.isdigit():
        # The legacy data schema defines the stable ID as <char_id>/<sample_index>.
        # This also repairs spreadsheet date conversion such as "6月18日".
        return f"{char_id}/{sample_index}"
    raise ValueError(f"cannot recover canonical sample_id from {sample_id!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge manual hard-set annotations safely.")
    parser.add_argument("--base", default="reviews/hardset_review.csv")
    parser.add_argument("--review", required=True, help="CSV exported by a reviewer or spreadsheet.")
    parser.add_argument("--output", default="reviews/hardset_review.csv")
    args = parser.parse_args()

    base_rows = _read_csv_with_fallback(args.base)
    review_rows = _read_csv_with_fallback(args.review)
    normalized_base_rows = [{**row, "sample_id": _canonical_sample_id(row)} for row in base_rows]
    base_by_id = {row["sample_id"]: row for row in normalized_base_rows}
    base_by_key = {_row_key(row): row for row in normalized_base_rows}

    merged = {row["sample_id"]: dict(row) for row in normalized_base_rows}
    updated, recovered_ids, ignored = 0, 0, 0
    for review in review_rows:
        # Blank tail rows from the template are not annotations.
        if not any(review.get(field, "").strip() for field in MANUAL_SIGNAL_FIELDS):
            ignored += 1
            continue
        target = base_by_id.get(review.get("sample_id", "").strip())
        if target is None:
            target = base_by_key.get(_row_key(review))
            if target is None:
                raise ValueError(
                    "cannot match reviewed row "
                    f"sample_id={review.get('sample_id', '')!r}, key={_row_key(review)!r}"
                )
            recovered_ids += 1
        target_id = target["sample_id"]
        for field in ANNOTATION_FIELDS:
            merged[target_id][field] = review.get(field, "").strip()
        updated += 1

    # Validate the actual annotated rows, not the still-empty template tail.
    for row in merged.values():
        if not row.get("reviewer"):
            continue
        for field in ANNOTATION_FIELDS[:6]:
            if row.get(field) not in {"0", "1"}:
                raise ValueError(f"{row['sample_id']}: {field} must be 0 or 1")
        if row.get("keep") not in {"yes", "no"}:
            raise ValueError(f"{row['sample_id']}: keep must be yes or no")

    write_csv_rows(args.output, [merged[row["sample_id"]] for row in normalized_base_rows], REVIEW_FIELDS)
    print(f"merged {updated} reviewed rows; recovered {recovered_ids} changed sample IDs; ignored {ignored} blank rows")
    print(f"wrote UTF-8 CSV to {args.output}")


if __name__ == "__main__":
    main()
