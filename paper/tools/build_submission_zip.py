"""Build the lean LaTeX archive uploaded to the SNAPP submission system.

The manuscript is the only root-level ``.tex`` file, so the submission system
can identify it as the main document.  The Electronic Supplementary Material
is deliberately excluded: it is uploaded through the separate
"Supplementary material" slot.

Only files that the compile actually needs are included, and every literal
``\\input``/``\\includegraphics``/``\\bibliography`` target is validated before
the archive is written.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

# Class, bibliography style and generated bibliography must travel with the
# source: the submission system may compile without running BibTeX.
ROOT_FILES = (
    "manuscript.tex",
    "manuscript.bbl",
    "references.bib",
    "sn-jnl.cls",
    "sn-basic.bst",
)

# Fragments pulled in by \input{...}; they are not standalone documents.
FRAGMENT_PATTERNS = ("sections/*.tex", "tables/*.tex")

DEPENDENCY_PATTERN = re.compile(
    r"\\(input|include|includegraphics|bibliography)\*?\s*"
    r"(?:\[[^\]]*\]\s*)?\{([^{}]+)\}"
)

SUFFIXES = {
    "input": (".tex",),
    "include": (".tex",),
    "includegraphics": (".pdf", ".png", ".jpg", ".jpeg"),
    "bibliography": (".bib",),
}


def strip_comments(text: str) -> str:
    """Drop commented-out lines so disabled examples are not treated as deps."""
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def resolve_reference(paper_root: Path, command: str, name: str) -> Path | None:
    target = paper_root / name.strip()
    candidates = [target]
    if not target.suffix:
        candidates.extend(target.with_suffix(s) for s in SUFFIXES[command])
    return next((p.resolve() for p in candidates if p.is_file()), None)


def collect(paper_root: Path) -> list[Path]:
    files: list[Path] = []
    missing: list[str] = []
    for name in ROOT_FILES:
        path = paper_root / name
        if path.is_file():
            files.append(path)
        else:
            missing.append(name)
    for pattern in FRAGMENT_PATTERNS:
        files.extend(sorted(p for p in paper_root.glob(pattern) if p.is_file()))
    if missing:
        raise FileNotFoundError(
            "Missing required submission files: " + ", ".join(missing)
        )

    # Resolve every referenced dependency and pull it into the archive.
    seen = {p.resolve() for p in files}
    queue = list(files)
    errors: list[str] = []
    while queue:
        source = queue.pop()
        if source.suffix != ".tex":
            continue
        for command, argument in DEPENDENCY_PATTERN.findall(
            strip_comments(source.read_text(encoding="utf-8"))
        ):
            names = argument.split(",") if command == "bibliography" else [argument]
            for name in names:
                found = resolve_reference(paper_root, command, name)
                where = f"{source.relative_to(paper_root)}: {name.strip()}"
                if found is None:
                    errors.append(f"Missing source dependency: {where}")
                    continue
                if not found.is_relative_to(paper_root):
                    errors.append(f"Dependency outside the paper directory: {where}")
                    continue
                if found not in seen:
                    seen.add(found)
                    files.append(found)
                    queue.append(found)

    if errors:
        raise FileNotFoundError("\n".join(errors))

    # Guard the main-document contract the submission system relies on.
    roots = [
        p
        for p in seen
        if p.parent == paper_root.resolve() and p.name not in {"ESM_1.tex"}
    ]
    tex_roots = sorted(p.name for p in roots if p.suffix == ".tex")
    if tex_roots != ["manuscript.tex"]:
        raise RuntimeError(
            "Archive must contain exactly one root-level .tex file named "
            f"manuscript.tex, found: {tex_roots}"
        )
    return sorted(files, key=lambda p: p.relative_to(paper_root).as_posix())


def build(paper_root: Path, output: Path) -> None:
    paper_root = paper_root.resolve()
    files = collect(paper_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = ZipInfo(
                path.relative_to(paper_root).as_posix(), date_time=FIXED_TIMESTAMP
            )
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    if output.stat().st_size == 0:
        raise RuntimeError(f"Created an empty archive: {output}")
    print(f"archive={output}")
    print(f"files={len(files)}")
    print(f"bytes={output.stat().st_size}")
    for path in files:
        print(f"  {path.relative_to(paper_root).as_posix()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--paper-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.paper_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
