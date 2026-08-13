"""Build journal-grade statistics from completed formal IJDAR artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.journal_statistics import build_journal_statistics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    args = parser.parse_args()
    result = build_journal_statistics(
        args.project_root,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
