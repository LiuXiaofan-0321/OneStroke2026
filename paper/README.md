# OneStroke IJDAR manuscript workspace

`manuscript.tex` follows the Springer Nature `sn-jnl` structure and uses the
`iicol` double-column option requested by the current IJDAR submission
guidelines. The abstract follows the required Purpose--Methods--Results--
Conclusion structure and stays within the journal's 150--250 word limit.

Obtain the current official Springer Nature LaTeX template and place
`sn-jnl.cls` plus its bibliography style files in this directory (or install
them in the TeX environment) before compiling. Do not copy an old class file
from a third-party repository.

The manuscript intentionally contains three unresolved result tokens:

```text
[TASK1_MAIN_BENCHMARK]
[CHARACTER_DISJOINT]
[SMARTPHONE]
```

These tokens must only be replaced with results from completed, auditable
experiments. They are not authoring suggestions and must never be silently
filled.

Before submission, the author team must also replace the author/affiliation,
funding, acknowledgements, code-availability, and provisional UniCalli
bibliography metadata placeholders.

Build the statistical tables first:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.build_journal_statistics
python -m onestroke_model.scripts.build_paper_latex_tables
```

Then compile, once the official Springer class is available:

```bash
pdflatex manuscript
bibtex manuscript
pdflatex manuscript
pdflatex manuscript
```

`supplementary/PROVENANCE.md` lists the formal artifacts allowed to support the
paper. Synthetic smoke outputs and self-comparison examples are excluded.
