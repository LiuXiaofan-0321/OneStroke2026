"""Build a self-contained LaTeX source archive for online editors."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
TOP_LEVEL_FILES = (
    "manuscript.tex",
    "supplementary.tex",
    "references.bib",
    "sn-jnl.cls",
    "sn-basic.bst",
    "README.md",
    "COLLABORATION.md",
    "AUTHOR_BIOGRAPHIES.md",
)
SOURCE_PATTERNS = (
    "sections/*.tex",
    "tables/*.tex",
    "figures/*.pdf",
    "figures/*.png",
    "supplementary/*.md",
)


def collect_files(paper_root: Path) -> list[Path]:
    files: set[Path] = set()
    missing: list[str] = []
    for name in TOP_LEVEL_FILES:
        path = paper_root / name
        if path.is_file():
            files.add(path)
        elif name not in {"AUTHOR_BIOGRAPHIES.md"}:
            missing.append(name)
    for pattern in SOURCE_PATTERNS:
        files.update(path for path in paper_root.glob(pattern) if path.is_file())
    if missing:
        raise FileNotFoundError(
            "Missing required online-package files: " + ", ".join(missing)
        )
    return sorted(files, key=lambda path: path.relative_to(paper_root).as_posix())


def build_archive(paper_root: Path, output: Path) -> None:
    files = collect_files(paper_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(paper_root).as_posix()
            info = ZipInfo(relative, date_time=FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    if output.stat().st_size == 0:
        raise RuntimeError(f"Created an empty archive: {output}")
    print(f"archive={output}")
    print(f"files={len(files)}")
    print(f"bytes={output.stat().st_size}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_archive(args.paper_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
