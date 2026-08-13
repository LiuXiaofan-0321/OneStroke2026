from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image

from onestroke_model.data.dataset_qc import build_dataset_qc
from onestroke_model.reproducibility import canonical_csv_sha256


def _write_sample(
    root: Path,
    sample_id: str,
    *,
    mismatch: bool = False,
    offset: int = 0,
) -> None:
    char_id, sample_index = sample_id.split("/")
    sample_dir = root / char_id / sample_index
    sample_dir.mkdir(parents=True)
    image = np.full((8, 8), 255, dtype=np.uint8)
    image[2:6, 2 + offset : 6 + offset] = 0
    if mismatch:
        image = np.full((8, 8), 255, dtype=np.uint8)
        image[:2, :2] = 0
    Image.fromarray(image).save(sample_dir / "0.jpg", quality=100, subsampling=0)
    masks = np.zeros((8, 8, 6), dtype=bool)
    masks[2:6, 2 + offset : 6 + offset, 0] = True
    masks[3, 3 + offset, 5] = True
    np.save(sample_dir / "0.npy", masks)
    filenames = (
        "mask_1.npy",
        "mask_2.npy",
        "mask_3.npy",
        "mask_4.npy",
        "mask_5.npy",
        "mask_key_point.npy",
    )
    for index, filename in enumerate(filenames):
        np.save(sample_dir / filename, masks[..., index])


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_dataset_qc_excludes_mismatch_and_exact_duplicate(tmp_path: Path) -> None:
    root = tmp_path / "data"
    _write_sample(root, "0/0")
    _write_sample(root, "0/1", offset=1)
    _write_sample(root, "1/0", mismatch=True)
    # Force an exact cross-character duplicate of 0/0.
    duplicate_dir = root / "2" / "0"
    duplicate_dir.mkdir(parents=True)
    (duplicate_dir / "0.jpg").write_bytes((root / "0" / "0" / "0.jpg").read_bytes())
    (duplicate_dir / "0.npy").write_bytes((root / "0" / "0" / "0.npy").read_bytes())

    manifest_rows = [
        {
            "sample_id": sample_id,
            "char_id": sample_id.split("/")[0],
            "sample_index": sample_id.split("/")[1],
            "has_all_masks": "true",
            "errors": "",
        }
        for sample_id in ("0/0", "0/1", "1/0", "2/0")
    ]
    manifest = tmp_path / "manifest.csv"
    _write_csv(manifest, manifest_rows)
    split_rows = [
        {"sample_id": "0/0", "char_id": "0", "split": "train"},
        {"sample_id": "0/1", "char_id": "0", "split": "train"},
        {"sample_id": "1/0", "char_id": "1", "split": "val"},
        {"sample_id": "2/0", "char_id": "2", "split": "test"},
    ]
    standard = tmp_path / "standard.csv"
    character = tmp_path / "character.csv"
    _write_csv(standard, split_rows)
    _write_csv(character, split_rows)

    report = build_dataset_qc(
        manifest,
        root,
        standard,
        character,
        tmp_path / "out",
    )

    assert report["complete_gt_sample_count"] == 4
    assert report["mismatch_sample_count"] == 1
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_noncanonical_sample_count"] == 1
    assert report["clean_sample_count"] == 2
    assert report["splits"]["standard"]["cross_split_exact_duplicate_group_count"] == 1
    assert report["reference_cache_used_as_ground_truth"] is False
    assert report["labels_generated_or_fabricated"] is False
    assert Path(report["outputs"]["clean_manifest"]).is_file()
    contract = Path(report["outputs"]["exclusion_contract_csv"])
    assert contract.is_file()
    assert report["outputs"]["exclusion_contract_csv_sha256"] == canonical_csv_sha256(
        contract
    )
    with contract.open(encoding="utf-8-sig", newline="") as handle:
        contract_rows = list(csv.DictReader(handle))
    assert {row["sample_id"] for row in contract_rows} == {"1/0", "2/0"}
    assert all(row["decision"] == "EXCLUDE" for row in contract_rows)
