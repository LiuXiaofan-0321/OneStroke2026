# OneStroke IJDAR manuscript workspace

## Target venue

- Journal: *International Journal on Document Analysis and Recognition*
  (IJDAR).
- Special Issue: *Computer Vision Systems for Document Analysis and
  Recognition*.
- Current submission deadline: 2026-09-20.
- Official call:
  <https://link.springer.com/collections/jaeiejghgj>
- Journal instructions:
  <https://link.springer.com/journal/10032/submission-guidelines>

The manuscript uses the Springer Nature `sn-jnl` template with:

```tex
\documentclass[iicol,pdflatex,sn-basic]{sn-jnl}
```

The local layout check used the official December 2024 Springer Nature
template package. Do not commit a copied `sn-jnl.cls`; download the current
official package before submission.

## Current scientific status

Completed:

- 18 formal segmentation runs: three architectures, two split protocols, and
  three seeds.
- QC-clean standard and character-disjoint results.
- controlled perturbation statistics and paired alignment ablation.
- inactive-channel score audit.
- diagnostic failure taxonomy.
- blinded three-rater structural validation on 150 natural pairs.
- retrospective aligned spatial-distribution similarity (ASDS) development
  with character-grouped out-of-fold internal validation.

Not yet submission-complete:

- funding, ethics/exemption wording,
  CRediT contributions, acknowledgements, and final code/data statements must
  be supplied by the team.

The full-sample result `rho=0.556` must be described as retrospective
development evidence, while the character-grouped out-of-fold
`rho=0.540` is an internal-validation estimate. Neither is an external or
prospective confirmation result because ASDS feature design followed
inspection of the original 150 ratings.

The generated 100-pair confirmatory candidate package is retained as an
optional future-study artifact and is not required for the present
submission.

## Rebuild development statistics

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.build_spatial_score_development
```

The tracked non-image results are written to:

```text
artifacts/paper_ijdar/spatial_score_development/
```

## Build the paper

Place the current official `sn-jnl.cls` and `sn-basic.bst` in a local TeX
search path, then:

```powershell
cd paper
pdflatex manuscript.tex
bibtex manuscript
pdflatex manuscript.tex
pdflatex manuscript.tex
```

Rebuild the development-stage human-association figure with:

```powershell
python figures/build_human_score_association.py
```

The current draft compiles to 17 A4 pages. The abstract has 243 words and six
keywords. The final LaTeX log contains no overfull boxes, undefined citations,
undefined references, or LaTeX/package warnings. The PDF is a review draft,
not a submission-ready final, until the placeholders listed above are closed.

## Provenance

`supplementary/PROVENANCE.md` lists the formal artifacts allowed to support the
paper. Synthetic smoke outputs and self-comparison demonstrations are excluded
from scientific claims.
