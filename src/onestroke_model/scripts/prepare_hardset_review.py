"""Prepare a portable, review-ready hard-case candidate set.

The score is only a triage aid.  It uses multi-channel overlap and mask geometry
to surface likely crossings or complex characters; the final difficulty labels
must always be decided by a human reviewer.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from onestroke_model.utils.io import ensure_dir, read_csv_rows, write_csv_rows


REVIEW_FIELDS = [
    "sample_id",
    "char_id",
    "sample_index",
    "split",
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


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _load_masks(row: dict[str, str]) -> np.ndarray | None:
    paths = [row.get(f"vec{i}_path", "") for i in range(1, 6)] + [row.get("keypoint_path", "")]
    if not all(paths):
        return None
    try:
        masks = [np.asarray(np.load(path), dtype=np.float32) > 0 for path in paths]
    except (OSError, ValueError):
        return None
    if len({mask.shape for mask in masks}) != 1 or masks[0].ndim != 2:
        return None
    return np.stack(masks, axis=0)


def _candidate_score(row: dict[str, str]) -> tuple[float, str]:
    masks = _load_masks(row)
    if masks is None:
        return 0.0, "标签不可读取，需人工确认"

    direction_masks = masks[:5]
    union = direction_masks.any(axis=0)
    union_pixels = max(int(union.sum()), 1)
    overlap_pixels = int((direction_masks.sum(axis=0) >= 2).sum())
    overlap_ratio = overlap_pixels / union_pixels

    occupied = int(direction_masks.reshape(5, -1).any(axis=1).sum())
    keypoint_ratio = float(masks[5].sum()) / union_pixels
    score = 100.0 * overlap_ratio + 4.0 * occupied + min(keypoint_ratio * 200.0, 8.0)
    reason = f"自动候选：多通道重叠 {overlap_ratio:.1%}，方向覆盖 {occupied}/5"
    return score, reason


def _choose_candidates(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    # Test cases are most valuable for reporting; validation cases supplement them.
    priority = {"test": 0, "val": 1, "train": 2}
    by_char: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_char[row["char_id"]].append(row)
    for bucket in by_char.values():
        bucket.sort(key=lambda r: (priority.get(r["split"], 9), -float(r["_score"]), r["sample_id"]))

    selected: list[dict[str, str]] = []
    # Round-robin prevents the hard set from becoming a few high-stroke characters.
    char_ids = sorted(by_char, key=lambda c: (-float(by_char[c][0]["_score"]), c))
    while char_ids and len(selected) < limit:
        next_char_ids: list[str] = []
        for char_id in char_ids:
            if len(selected) >= limit:
                break
            bucket = by_char[char_id]
            if bucket:
                selected.append(bucket.pop(0))
            if bucket:
                next_char_ids.append(char_id)
        char_ids = next_char_ids
    return selected


def _draw_contact_sheet(rows: list[dict[str, str]], output: str | Path, columns: int) -> None:
    cell_w, cell_h, title_h = 220, 250, 42
    columns = max(columns, 1)
    num_rows = max((len(rows) + columns - 1) // columns, 1)
    canvas = Image.new("RGB", (columns * cell_w, num_rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for i, row in enumerate(rows):
        x, y = (i % columns) * cell_w, (i // columns) * cell_h
        image_path = Path(row["image_path"])
        try:
            image = Image.open(image_path).convert("RGB")
            image.thumbnail((cell_w - 16, cell_h - title_h - 12))
            image_x = x + (cell_w - image.width) // 2
            image_y = y + title_h + (cell_h - title_h - image.height) // 2
            canvas.paste(image, (image_x, image_y))
        except OSError:
            draw.text((x + 8, y + title_h + 8), "image unavailable", fill="red", font=font)
        draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline="#999999")
        draw.text((x + 8, y + 6), f"{row['sample_id']}  {row['split']}", fill="black", font=font)
        draw.text((x + 8, y + 22), f"score {float(row['_score']):.1f}", fill="#555555", font=font)
    output_path = Path(output)
    ensure_dir(output_path.parent)
    canvas.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare hard-set candidates and a contact sheet for review.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--splits", required=True)
    parser.add_argument("--output", default="reviews/hardset_review.csv")
    parser.add_argument("--contact-sheet", default="artifacts/data_audit/hardset_candidates.png")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--columns", type=int, default=5)
    args = parser.parse_args()

    split_by_id = {row["sample_id"]: row["split"] for row in read_csv_rows(args.splits)}
    manifest = read_csv_rows(args.manifest)
    candidates: list[dict[str, str]] = []
    # A hard set is an evaluation asset.  Training samples are deliberately
    # excluded so it cannot accidentally become a favorable training report.
    evaluation_splits = {"val", "test"}
    eligible = [
        row
        for row in manifest
        if _truthy(row.get("has_all_masks", ""))
        and not row.get("errors")
        and split_by_id.get(row["sample_id"]) in evaluation_splits
    ]
    print(f"scoring {len(eligible)} val/test samples...", flush=True)
    for row in eligible:
        score, reason = _candidate_score(row)
        candidates.append({**row, "split": split_by_id[row["sample_id"]], "_score": f"{score:.6f}", "_reason": reason})

    selected = _choose_candidates(candidates, args.limit)
    review_rows = [
        {
            "sample_id": row["sample_id"],
            "char_id": row.get("char_id", ""),
            "sample_index": row.get("sample_index", ""),
            "split": row["split"],
            "priority": "high" if row["split"] == "test" else "medium",
            "notes": f"{row['_reason']}；需人工复核",
        }
        for row in selected
    ]
    write_csv_rows(args.output, review_rows, REVIEW_FIELDS)
    _draw_contact_sheet(selected, args.contact_sheet, args.columns)
    counts: dict[str, int] = defaultdict(int)
    for row in selected:
        counts[row["split"]] += 1
    print(f"wrote {len(selected)} review candidates to {args.output}")
    print(f"wrote contact sheet to {args.contact_sheet}")
    print("split counts:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
