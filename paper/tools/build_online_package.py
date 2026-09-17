"""Build a self-contained LaTeX source archive for online editors."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
TOP_LEVEL_FILES = (
    "manuscript.tex",
    "ESM_1.tex",
    "references.bib",
    "sn-jnl.cls",
    "sn-basic.bst",
    "README.md",
    "COLLABORATION.md",
    "AUTHOR_BIOGRAPHIES.md",
)
SOURCE_PATTERNS = (
    "sections/**/*.tex",
    "tables/**/*.tex",
    "figures/**/*.pdf",
    "figures/**/*.png",
    "figures/**/*.jpg",
    "figures/**/*.jpeg",
    "figures/**/*.svg",
    "figures/**/*.tiff",
    "figures/**/*.py",
    "figures/**/*.json",
    "figures/**/*.csv",
    "figures/**/*.md",
    "supplementary/*.md",
    "tools/*.py",
    "revision_*.md",
    "REVISION_*.md",
)
EXCLUDED_DIRECTORIES = {"__pycache__", "deliverables", "releases", "qa"}
DEPENDENCY_PATTERN = re.compile(
    r"\\(input|include|includegraphics|bibliography)\*?\s*"
    r"(?:\[[^\]]*\]\s*)?\{([^{}]+)\}"
)


def validate_dependencies(paper_root: Path, files: set[Path]) -> None:
    """Reject missing or omitted literal file references before writing the zip."""
    errors: list[str] = []
    suffixes = {
        "input": (".tex",),
        "include": (".tex",),
        "includegraphics": (".pdf", ".png", ".jpg", ".jpeg"),
        "bibliography": (".bib",),
    }
    for source in sorted(files):
        if source.suffix != ".tex":
            continue
        # The manuscript uses literal, project-relative references. Ignore
        # comments so disabled examples do not become archive requirements.
        content = re.sub(r"(?<!\\)%[^\n]*", "", source.read_text(encoding="utf-8"))
        for command, argument in DEPENDENCY_PATTERN.findall(content):
            names = argument.split(",") if command == "bibliography" else [argument]
            for name in names:
                dependency = paper_root / name.strip()
                candidates = [dependency]
                if not dependency.suffix:
                    candidates.extend(
                        dependency.with_suffix(suffix) for suffix in suffixes[command]
                    )
                found = next((path.resolve() for path in candidates if path.is_file()), None)
                reference = f"{source.relative_to(paper_root)}: {name.strip()}"
                if found is None:
                    errors.append(f"Missing source dependency: {reference}")
                elif not found.is_relative_to(paper_root):
                    errors.append(f"Dependency outside the paper directory: {reference}")
                elif found not in files:
                    errors.append(f"Dependency omitted from archive: {reference}")
    if errors:
        raise FileNotFoundError("\n".join(errors))


def collect_files(paper_root: Path) -> list[Path]:
    paper_root = paper_root.resolve()
    files: set[Path] = set()
    missing: list[str] = []
    for name in TOP_LEVEL_FILES:
        path = paper_root / name
        if path.is_file():
            files.add(path)
        elif name not in {"AUTHOR_BIOGRAPHIES.md"}:
            missing.append(name)
    for pattern in SOURCE_PATTERNS:
        files.update(
            path
            for path in paper_root.glob(pattern)
            if path.is_file()
            and not EXCLUDED_DIRECTORIES.intersection(path.relative_to(paper_root).parts)
        )
    if missing:
        raise FileNotFoundError(
            "Missing required online-package files: " + ", ".join(missing)
        )
    validate_dependencies(paper_root, files)
    return sorted(files, key=lambda path: path.relative_to(paper_root).as_posix())


def build_archive(paper_root: Path, output: Path) -> None:
    paper_root = paper_root.resolve()
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
