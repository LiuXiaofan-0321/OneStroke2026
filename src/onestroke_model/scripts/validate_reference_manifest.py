from __future__ import annotations

import argparse
from pathlib import Path

from onestroke_model.config import load_yaml
from onestroke_model.utils.io import read_csv_rows, write_json


REQUIRED_COLUMNS = {
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
    "author_id",
    "script_style",
    "is_synthetic",
    "review_status",
    "reviewer",
    "review_date",
}

ALLOWED_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def _registry_styles(registry_path: str | Path) -> dict[str, dict[str, object]]:
    registry = load_yaml(registry_path)
    styles = registry.get("styles", [])
    if not isinstance(styles, list):
        raise ValueError("style registry field 'styles' must be a list")
    result = {}
    for style in styles:
        if not isinstance(style, dict) or not style.get("style_id"):
            raise ValueError("each style registry entry requires style_id")
        style_id = str(style["style_id"])
        if style_id in result:
            raise ValueError(f"duplicate style_id in registry: {style_id}")
        result[style_id] = style
    return result


def validate_reference_manifest(
    manifest_path: str | Path,
    registry_path: str | Path,
    check_files: bool = False,
    require_approved: bool = False,
) -> dict[str, object]:
    rows = read_csv_rows(manifest_path)
    manifest_path = Path(manifest_path)
    styles = _registry_styles(registry_path)
    columns = set(rows[0]) if rows else set()
    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    errors: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    approved = 0

    for row_number, row in enumerate(rows, start=2):
        reference_id = row.get("reference_id", "").strip()
        style_id = row.get("style_id", "").strip()
        review_status = row.get("review_status", "").strip().lower()
        image_path = row.get("image_path", "").strip()
        if not reference_id:
            errors.append({"row": row_number, "field": "reference_id", "message": "required"})
        elif reference_id in seen_ids:
            errors.append({"row": row_number, "field": "reference_id", "message": "duplicate"})
        seen_ids.add(reference_id)
        if style_id not in styles:
            errors.append({"row": row_number, "field": "style_id", "message": "not in registry"})
            continue
        style = styles[style_id]
        if row.get("schema_version", "").strip() != "1":
            errors.append({"row": row_number, "field": "schema_version", "message": "must be 1"})
        if len(row.get("target_char", "").strip()) != 1:
            errors.append({"row": row_number, "field": "target_char", "message": "must be one character"})
        if not image_path:
            errors.append({"row": row_number, "field": "image_path", "message": "required"})
        elif check_files and not (manifest_path.parent / image_path).exists():
            errors.append({"row": row_number, "field": "image_path", "message": "file not found"})
        if not row.get("source_type", "").strip():
            errors.append({"row": row_number, "field": "source_type", "message": "required"})
        if row.get("is_synthetic", "").strip().lower() not in {"true", "false"}:
            errors.append({"row": row_number, "field": "is_synthetic", "message": "must be true or false"})
        if review_status not in ALLOWED_REVIEW_STATUSES:
            errors.append(
                {"row": row_number, "field": "review_status", "message": "must be pending, approved, or rejected"}
            )
        for field in ("author_id", "script_style"):
            expected = str(style.get(field, "")).strip()
            actual = row.get(field, "").strip()
            if expected and actual != expected:
                errors.append(
                    {"row": row_number, "field": field, "message": f"must match registry value: {expected}"}
                )
        if review_status == "approved":
            approved += 1
            required = [
                "source_url",
                "source_license",
                "source_work_id",
                "source_version",
                "reviewer",
                "review_date",
            ]
            for field in required:
                if not row.get(field, "").strip():
                    errors.append({"row": row_number, "field": field, "message": "required for approved reference"})
            if not bool(style.get("enabled", False)):
                errors.append(
                    {"row": row_number, "field": "style_id", "message": "style is not enabled"}
                )
        elif require_approved:
            errors.append({"row": row_number, "field": "review_status", "message": "must be approved"})

    return {
        "manifest": str(manifest_path.resolve()),
        "registry": str(Path(registry_path).resolve()),
        "num_rows": len(rows),
        "num_approved": approved,
        "missing_columns": missing_columns,
        "errors": errors,
        "valid": not missing_columns and not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an audited calligraphy reference manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--registry", default="configs/style_registry.yaml")
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument("--require-approved", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = validate_reference_manifest(
        args.manifest,
        args.registry,
        check_files=args.check_files,
        require_approved=args.require_approved,
    )
    print(report)
    if args.output:
        write_json(args.output, report)
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
