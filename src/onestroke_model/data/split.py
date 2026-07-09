from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from onestroke_model.utils.io import read_csv_rows, write_csv_rows


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def choose_group_key(row: dict[str, str]) -> str:
    for key in ("writer_id", "source_id", "sample_index", "split_group_key"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return row["sample_id"]


def _stable_sort_key(value: str) -> tuple[int, str]:
    # Keep numeric sample indexes in natural order; fallback to deterministic hash.
    try:
        return int(value), value
    except ValueError:
        h = hashlib.sha1(value.encode("utf-8")).hexdigest()
        return int(h[:8], 16), value


def assign_splits(
    manifest_path: str | Path,
    output_path: str | Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> dict[str, object]:
    rows = read_csv_rows(manifest_path)
    usable = [r for r in rows if _truthy(r.get("has_all_masks", "")) and not r.get("errors", "")]
    groups = sorted({choose_group_key(r) for r in usable}, key=_stable_sort_key)
    n = len(groups)
    n_train = round(n * train_ratio)
    n_val = round(n * val_ratio)
    train_groups = set(groups[:n_train])
    val_groups = set(groups[n_train : n_train + n_val])

    split_rows: list[dict[str, object]] = []
    for row in usable:
        group = choose_group_key(row)
        if group in train_groups:
            split = "train"
        elif group in val_groups:
            split = "val"
        else:
            split = "test"
        split_rows.append(
            {
                "sample_id": row["sample_id"],
                "char_id": row.get("char_id", ""),
                "sample_index": row.get("sample_index", ""),
                "group_key": group,
                "split": split,
            }
        )

    write_csv_rows(
        output_path,
        split_rows,
        ["sample_id", "char_id", "sample_index", "group_key", "split"],
    )
    counts = Counter(r["split"] for r in split_rows)
    return {
        "manifest": str(manifest_path),
        "output": str(output_path),
        "num_usable_samples": len(split_rows),
        "num_groups": n,
        "grouping_rule": "writer_id > source_id > sample_index > split_group_key > sample_id",
        "counts": dict(counts),
    }
