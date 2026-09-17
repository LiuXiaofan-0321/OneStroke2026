# Revision build notes

The maintained LaTeX entry points are `manuscript.tex` and `ESM_1.tex`.
The GitHub Actions build now uses those names consistently when compiling,
checking logs, collecting PDFs, and publishing its build artifact.

The online-editor archive now includes nested figure directories, including
the `figures/redrawn/` PDFs used by the manuscript and `figures/revision/`
assets when present. Figure builders and their local JSON/CSV metadata,
SVGs, and Markdown notes are retained alongside frozen image assets.
Release snapshots, deliverables, QA directories, and Python caches are excluded.
The package is self-contained for LaTeX compilation. Rebuilding historical
scientific figures may still require repository artifacts or model checkpoints
documented by their builders; the archive does not substitute for those inputs.

Before writing the zip, the builder checks literal `input`, `include`,
`includegraphics`, and `bibliography` references in packaged TeX sources.
It fails with the referring source and filename if a dependency is missing,
outside the paper directory, or omitted from the archive.

Generated root-level manuscript and supplement PDFs remain build products;
they are not bundled into the LaTeX source archive.

Validation performed during this revision:

- Python syntax and whitespace checks passed.
- All literal dependencies in the 23 packaged TeX sources resolved and were
  included; the new Figure 2 PDF and its Python builder were also collected.
- Deliberately removing a referenced figure from the collected file set
  triggered the expected archive-validation failure.
- The collected paths contained no release snapshots, deliverables,
  QA directories, or Python caches.

The archive check runs again automatically whenever the final package is built.
Final manuscript and supplement typesetting are checked separately from this
source-dependency validation.
