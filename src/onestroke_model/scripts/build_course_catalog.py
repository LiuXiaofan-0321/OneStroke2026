from __future__ import annotations

import argparse
import json

from onestroke_model.course_packs import build_course_catalog, load_course_packs
from onestroke_model.utils.io import write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the frontend-safe course pack and character catalog."
    )
    parser.add_argument("--course-config", default="configs/course_packs.yaml")
    parser.add_argument("--output", default="artifacts/course_packs/catalog.json")
    parser.add_argument("--require-cache", action="store_true")
    args = parser.parse_args()
    catalog = build_course_catalog(
        load_course_packs(args.course_config), require_cache=args.require_cache
    )
    write_json(args.output, catalog)
    print(
        json.dumps({"courses": len(catalog["courses"]), "output": args.output}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
