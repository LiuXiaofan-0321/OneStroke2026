from __future__ import annotations

import argparse

from onestroke_model.utils.io import read_csv_rows, write_csv_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a manual hard-case review template.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/data_audit/hardset_template.csv")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    rows = [r for r in read_csv_rows(args.manifest) if r.get("has_all_masks") == "true" and not r.get("errors")]
    by_char: dict[str, list[dict[str, str]]] = {}
    for row in sorted(rows, key=lambda r: (r.get("sample_index", ""), r["sample_id"])):
        by_char.setdefault(row.get("char_id", ""), []).append(row)

    selected: list[dict[str, str]] = []
    char_ids = sorted(by_char)
    cursor = 0
    while len(selected) < args.limit and char_ids:
        char_id = char_ids[cursor % len(char_ids)]
        bucket = by_char[char_id]
        if bucket:
            selected.append(bucket.pop(0))
        char_ids = [c for c in char_ids if by_char[c]]
        cursor += 1
    out_rows = [
        {
            "sample_id": r["sample_id"],
            "char_id": r.get("char_id", ""),
            "sample_index": r.get("sample_index", ""),
            "image_path": r.get("image_path", ""),
            "hard_crossing": "",
            "hard_adhesion": "",
            "hard_endpoint": "",
            "hard_line_width": "",
            "hard_background": "",
            "reviewer": "",
            "notes": "",
        }
        for r in selected
    ]
    write_csv_rows(
        args.output,
        out_rows,
        [
            "sample_id",
            "char_id",
            "sample_index",
            "image_path",
            "hard_crossing",
            "hard_adhesion",
            "hard_endpoint",
            "hard_line_width",
            "hard_background",
            "reviewer",
            "notes",
        ],
    )
    print(f"wrote {len(out_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
