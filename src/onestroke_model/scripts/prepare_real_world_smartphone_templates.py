"""Create smartphone/unseen-writer study metadata templates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.real_world_protocol import write_real_world_templates


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare real-world study CSV templates.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/real_world/templates",
    )
    args = parser.parse_args()
    metadata = write_real_world_templates(args.output_dir)
    print(
        json.dumps(
            {
                **metadata,
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
