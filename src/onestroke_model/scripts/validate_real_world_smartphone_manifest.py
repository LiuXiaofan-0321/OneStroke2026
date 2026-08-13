"""Validate consent, ethics, schema, and image readiness for real-world data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from onestroke_model.real_world_protocol import validate_real_world_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a smartphone study manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-local-images", action="store_true")
    args = parser.parse_args()
    manifest = Path(args.manifest)
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = validate_real_world_rows(
        rows,
        require_local_images=args.require_local_images,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
