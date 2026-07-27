from __future__ import annotations

import argparse
import hashlib
import io
import os
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image

from onestroke_model.constants import SCHEMA_VERSION
from onestroke_model.utils.io import ensure_dir, write_csv_rows, write_json


DATASET_URL = (
    "https://www.modelscope.cn/datasets/CalliTongji/"
    "Calli-Tongji_A_Dataset_of_Historical_Calligraphy_Styles"
)
DATASET_LICENSE = "CC-BY-NC-4.0"
DATASET_WORK_ID = "calli_tongji_beta"

MANIFEST_FIELDNAMES = [
    "schema_version",
    "reference_id",
    "style_id",
    "target_char",
    "image_path",
    "source_type",
    "source_url",
    "source_license",
    "source_work_id",
    "source_version",
    "bbox_left",
    "bbox_top",
    "bbox_right",
    "bbox_bottom",
    "author_id",
    "script_style",
    "is_synthetic",
    "review_status",
    "reviewer",
    "review_date",
    "notes",
]

STYLE_SPECS = {
    "欧阳询-楷": {
        "style_id": "ouyang_xun_regular_calli_tongji_beta",
        "author_id": "ouyang_xun",
        "script_style": "kaishu",
    },
    "王羲之-行": {
        "style_id": "wang_xizhi_running_calli_tongji_beta",
        "author_id": "wang_xizhi",
        "script_style": "xingshu",
    },
}


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_image(raw: bytes, member: str) -> tuple[int, int]:
    with Image.open(io.BytesIO(raw)) as image:
        image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        if image.mode != "RGB":
            raise ValueError(f"{member}: expected RGB image, got {image.mode}")
        if image.size != (256, 256):
            raise ValueError(f"{member}: expected 256x256 image, got {image.size}")
        return image.size


def import_calli_tongji(
    archive_path: str | Path,
    image_dir: str | Path,
    manifest_path: str | Path,
    reviewer: str = "dataset_import",
    review_date: str | None = None,
) -> dict[str, object]:
    """Extract the two verified Calli-Tongji Beta styles and create a manifest."""
    archive_path = Path(archive_path)
    image_dir = ensure_dir(image_dir)
    manifest_path = Path(manifest_path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"archive not found: {archive_path}")

    archive_hash = _archive_sha256(archive_path)
    review_date = review_date or date.today().isoformat()
    rows: list[dict[str, object]] = []
    style_counts = {spec["style_id"]: 0 for spec in STYLE_SPECS.values()}

    with zipfile.ZipFile(archive_path) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise ValueError(f"corrupt archive member: {corrupt_member}")
        for member in sorted(archive.namelist()):
            parts = Path(member).parts
            if len(parts) != 3 or parts[0] != "Calli-Tongji" or not member.lower().endswith(".png"):
                continue
            category = parts[1]
            spec = STYLE_SPECS.get(category)
            if spec is None:
                continue
            target_char = Path(parts[2]).stem
            if len(target_char) != 1:
                raise ValueError(f"{member}: expected a one-character filename")
            raw = archive.read(member)
            width, height = _validate_image(raw, member)
            image_hash = hashlib.sha256(raw).hexdigest()
            output_dir = ensure_dir(image_dir / spec["style_id"])
            output_path = output_dir / f"{target_char}_{image_hash[:12]}.png"
            if output_path.exists() and hashlib.sha256(output_path.read_bytes()).hexdigest() != image_hash:
                raise ValueError(f"refusing to overwrite different image: {output_path}")
            if not output_path.exists():
                output_path.write_bytes(raw)
            relative_path = os.path.relpath(output_path, manifest_path.parent).replace("\\", "/")
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "reference_id": f"{spec['style_id']}:{ord(target_char):04x}:{image_hash[:12]}",
                    "style_id": spec["style_id"],
                    "target_char": target_char,
                    "image_path": relative_path,
                    "source_type": "official_open_dataset",
                    "source_url": DATASET_URL,
                    "source_license": DATASET_LICENSE,
                    "source_work_id": DATASET_WORK_ID,
                    "source_version": f"sha256:{archive_hash}",
                    "bbox_left": 0,
                    "bbox_top": 0,
                    "bbox_right": width,
                    "bbox_bottom": height,
                    "author_id": spec["author_id"],
                    "script_style": spec["script_style"],
                    "is_synthetic": "false",
                    "review_status": "approved",
                    "reviewer": reviewer,
                    "review_date": review_date,
                    "notes": f"Imported from {category}; source member: {member}",
                }
            )
            style_counts[spec["style_id"]] += 1

    if not rows:
        raise ValueError("no configured Calli-Tongji images were found in archive")
    write_csv_rows(manifest_path, rows, MANIFEST_FIELDNAMES)
    report = {
        "archive": str(archive_path.resolve()),
        "archive_sha256": archive_hash,
        "image_dir": str(image_dir.resolve()),
        "manifest": str(manifest_path.resolve()),
        "num_references": len(rows),
        "style_counts": style_counts,
        "source_url": DATASET_URL,
        "source_license": DATASET_LICENSE,
    }
    write_json(manifest_path.with_suffix(".report.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Import verified Calli-Tongji Beta reference characters.")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--image-dir", default="references/images/calli_tongji_beta")
    parser.add_argument("--manifest", default="references/calli_tongji_beta_manifest.csv")
    parser.add_argument("--reviewer", default="dataset_import")
    parser.add_argument("--review-date", default=None)
    args = parser.parse_args()

    report = import_calli_tongji(
        archive_path=args.archive,
        image_dir=args.image_dir,
        manifest_path=args.manifest,
        reviewer=args.reviewer,
        review_date=args.review_date,
    )
    print(report)


if __name__ == "__main__":
    main()
