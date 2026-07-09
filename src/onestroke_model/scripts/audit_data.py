from __future__ import annotations

import argparse
from pathlib import Path

from onestroke_model.data.audit import MANIFEST_FIELDNAMES, audit_data
from onestroke_model.utils.io import ensure_dir, write_csv_rows, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit old OneStroke data and build manifest.csv.")
    parser.add_argument("--data-root", required=True, help="Path to StrokeSegmentation/data/output_img.")
    parser.add_argument("--out-dir", default="artifacts/data_audit")
    parser.add_argument("--data-version", default="old_onestroke")
    args = parser.parse_args()

    out_dir = ensure_dir(args.out_dir)
    result = audit_data(args.data_root, data_version=args.data_version)
    write_csv_rows(out_dir / "manifest.csv", result.rows, MANIFEST_FIELDNAMES)
    write_json(out_dir / "audit_report.json", result.report)
    print(f"manifest: {Path(out_dir / 'manifest.csv').resolve()}")
    print(f"report:   {Path(out_dir / 'audit_report.json').resolve()}")
    print(result.report)


if __name__ == "__main__":
    main()

