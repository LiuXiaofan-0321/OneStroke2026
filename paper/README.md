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
\documentclass[iicol,pdflatex,sn-basic,Numbered]{sn-jnl}
```

The local layout check used the official December 2024 Springer Nature
template package. The corresponding `sn-jnl.cls` and `sn-basic.bst` are
tracked in this directory so that local builds, GitHub Actions, and imported
online projects compile from the same source. Before final submission, compare
these copies against the template currently supplied by Springer Nature.

## Collaborative editing

GitHub is the source of truth for the manuscript. The workflow
`.github/workflows/build-paper.yml` compiles the main manuscript and
supplementary material after every paper-related push or pull request. Its
artifact contains:

- `manuscript.pdf`;
- `supplementary.pdf`;
- `OneStroke2026_online_latex.zip`, a self-contained source package that can
  be imported manually into Overleaf or another online LaTeX editor.

Generated root-level PDFs are intentionally ignored to prevent a stale local
PDF from being mistaken for the current source. Audited frozen snapshots are
stored under `releases/<date>/`; routine builds should be downloaded from the
corresponding GitHub Actions run.

The three-author branch and review procedure is documented in
`COLLABORATION.md`. Do not edit the GitHub and online-editor copies
independently; merge accepted edits into GitHub before starting another
editing round.

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
- paired direct-ink ASDS ablation on all 150 rated pairs, using the same
  alignment and frozen score specification.

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

The direct-ink ablation finds near-equivalent human association for parsed
union and thresholded source ink (`rho=0.55623` versus `0.55583`;
paired difference 95% CI `[-0.01011, 0.01030]`). This supports ASDS as a
silhouette descriptor and prevents its scalar performance from being used as
the justification for six-channel parsing. Parsing remains necessary for
direction- and endpoint-level evidence.

## Rebuild development statistics

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.build_spatial_score_development
python -m onestroke_model.scripts.build_direct_ink_asds
```

The tracked non-image results are written to:

```text
artifacts/paper_ijdar/spatial_score_development/
```

## Build the paper

The tracked `sn-jnl.cls` and `sn-basic.bst` make the paper directory
self-contained. Build from the repository root with:

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

Build the frozen segmentation qualitative figure with:

```powershell
$env:PYTHONPATH = "$PWD\..\src"
python figures/build_segmentation_qualitative.py --device cuda
```

This builder verifies the recorded SHA-256 values and refuses substitute
weights. It requires the seed-20260811 formal U-Net, DeepLabV3+, and
SegFormer-B2 checkpoints from both `main_qc` and `character_disjoint` runs.
The figure is inserted automatically when
`figures/segmentation_qualitative.pdf` exists. The large formal checkpoints
are not currently stored in Git; recover them from the Task 1 run directory
before the submission PDF is frozen.

Build the separate supplementary statistical tables with:

```powershell
cd paper
pdflatex supplementary.tex
pdflatex supplementary.tex
```

The main manuscript refers to these as Supplementary Tables S1 and S2.

Create a clean source archive for an online LaTeX editor with:

```powershell
python paper/tools/build_online_package.py `
  --output paper/deliverables/OneStroke2026_online_latex.zip
```

Draft 50--100-word biographies are in `AUTHOR_BIOGRAPHIES.md`; each author
must approve the text and supply a separate portrait photograph.

The current main draft is 19 A4 pages before insertion of the three-model
qualitative figure; the two full statistical tables have been moved to a
two-page supplementary PDF. The abstract has 243 words and six keywords. The
current main-manuscript LaTeX log contains no overfull boxes, undefined
citations, undefined references, or LaTeX/package warnings. The PDF remains a
review draft until the qualitative figure is inserted and institutional
ethics/exemption wording is confirmed.

## Provenance

`supplementary/PROVENANCE.md` lists the formal artifacts allowed to support the
paper. Synthetic smoke outputs and self-comparison demonstrations are excluded
from scientific claims.
