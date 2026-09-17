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
- `ESM_1.pdf` (Online Resource 1, the electronic supplementary material);
- `OneStroke2026_online_latex.zip`, a self-contained source package that can
  be imported manually into Overleaf or another online LaTeX editor.

Generated root-level PDFs are intentionally ignored to prevent a stale local
PDF from being mistaken for the current source. Audited frozen snapshots are
stored under `releases/<date>/`; routine builds should be downloaded from the
corresponding GitHub Actions run.

Revision log:

- `2026-09-17` *submission*: Introduction opening sentence on calligraphy as
  traditional Chinese culture and its script styles; in-figure and
  body-text explanation for Fig. 3; the same cultural framing condensed into
  the first abstract sentence; Fig. 1 panel (a) extended from one to three
  same-character cross-style pairs; tightened float spacing so the manuscript
  stays within 20 pages. See `REVISION_2026-09-17.md` and
  `releases/2026-09-17-submission/`.
- `2026-09-05` Fable 5.1 revision: redrawn Figs. 2, 3, and 6. See
  `REVISION_2026-09-05.md`.
- `2026-08-22` v2 and `2026-08-21`: earlier audited drafts.

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

- the "Not applicable" ethics-approval and informed-consent statements,
  the data-availability statement, and the Calli-Tongji attribution were
  written from the project records on 2026-09-03 and must be confirmed by
  every author before submission; author biographies and photographs are
  collected by the submission system separately.

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

Scientific prose calls the sixth output the **endpoint channel**. The literal
identifier `keypoint` is retained only in the versioned software schema,
configuration files, and historical result fields for backward compatibility.

The formal initialization protocols are: U-Net from random initialization;
DeepLabV3+ with an ImageNet-1K-pretrained ResNet-50 encoder and randomly
initialized ASPP/decoder/output head; and SegFormer-B2 from
`nvidia/segformer-b2-finetuned-ade-512-512`, with compatible encoder/decode
parameters loaded, the incompatible classifier replaced by a random
six-channel head, and all layers fine-tuned.

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

Build Figures 1--3 and 5--7 from frozen local artifacts with:

```powershell
python figures/build_submission_figures.py
```

This command writes vector PDF, high-resolution PNG, and
`figures/figure_provenance_manifest.json`. Figure 4 remains separate because
its builder requires all six formal checkpoints and validates every recorded
SHA-256 before using either inference or a prediction cache.

The active manuscript uses the retained vector figures in `figures/redrawn/`
and the revisions in `figures/revision/`: manuscript Figures 2, 3, and 6
(2026-09-05) and Figure 1 (2026-09-17). The new revisions provide native vector text and
reproducible Python builders:

```bash
python paper/figures/revision/build_figure1.py
python paper/figures/revision/build_figure2.py
python paper/figures/revision/build_figure3.py
python paper/figures/revision/build_figure6.py
```

Run these commands from the repository root. They use the frozen PDF image
objects and, for Figure 6, the tracked 150-pair result table. They do not
require missing image datasets or model checkpoints. Each builder records
source hashes and the mapping of original tiles to revised panels. They
recompose existing observations; they do not revalidate the underlying masks.
`build_figure1.py` additionally requires the frozen reference cache
(`references/cache/segformer_b2_v1/`) and the Calli-Tongji source images,
which are not tracked in Git; without them only the PDF/JSON provenance can be
inspected. It carries panels (b)--(e) over as vector PDF content and rebuilds
panel (a) only.

The historical `figures/redraw/` scripts named in the previous README are
not present in this checkout. Their outputs in `figures/redrawn/` remain
frozen. Do not claim that all seven historical figures can be regenerated
from the missing scripts. Current revision notes document this boundary.

The revisions retain the semantic channel colours and use sans-serif vector
labels, direct channel names, and a restrained hierarchy. Figure 2 groups
annotation sources, overlapping labels, and the six channels into three
panels. Figure 3 separates quality control, the 40 project identities, and
all seven external cross-style pairs. Figure 6 retains all 150 observations
and distinguishes observed association from formal equivalence.

The frozen renders in `figures/` are kept unchanged as the provenance source.

Build the frozen segmentation qualitative figure with:

```powershell
$env:PYTHONPATH = "$PWD\..\src"
python figures/build_segmentation_qualitative.py `
  --output figures/figure4_segmentation_qualitative.pdf `
  --device cuda
```

This builder verifies the recorded SHA-256 values and refuses substitute
weights. It requires the seed-20260811 formal U-Net, DeepLabV3+, and
SegFormer-B2 checkpoints from both `main_qc` and `character_disjoint` runs.
The tracked `figures/figure4_segmentation_qualitative.pdf` and high-resolution
PNG were generated from those frozen artifacts and are inserted directly into
the manuscript. The sidecar provenance file records the cases, protocols,
checkpoint hashes, and threshold-file hashes. The large formal checkpoints
are deliberately excluded from Git; recover them from the Task 1 run
directory only when the figure itself must be rebuilt.

Build the separate supplementary statistical tables with:

```powershell
cd paper
pdflatex ESM_1.tex
pdflatex ESM_1.tex
```

Following the Springer ESM convention, the main manuscript refers to the
supplement as "Online Resource 1" (Tables S1--S4, Notes S5--S6), and the
file is named `ESM_1.tex`/`ESM_1.pdf`.

Create a clean source archive for an online LaTeX editor with:

```powershell
python paper/tools/build_online_package.py `
  --output paper/deliverables/OneStroke2026_online_latex.zip
```

Draft 50--100-word biographies are in `AUTHOR_BIOGRAPHIES.md`; each author
must approve the text and supply a separate portrait photograph.

The manuscript is organized around one narrative: concrete phenomenon
(same character, different local structure) -> four computer-vision
challenges C1--C4 -> research questions RQ1--RQ4 -> method and experiments
-> results answered per RQ -> bounded contributions. The section files are:

```text
sections/01_introduction.tex        phenomenon, C1--C4, RQ1--RQ4, contributions, scope
sections/02_related_work.tex        prior work only (no self-description)
sections/03_data_resources.tex      corpus, annotation contract, QC, splits, reference library, cohorts
sections/04_method.tex              parser, registration, scores, evidence contract
sections/05_experimental_setup.tex  training/evaluation parameters and statistics per RQ
sections/06_results_discussion.tex  results and interpretation per RQ, with explicit answers
sections/07_discussion.tex          cross-RQ discussion and limitations
sections/08_conclusion.tex          conclusion by RQ
```

Seven formal figures are used, numbered by first reference: the pipeline and
the motivating cross-style pairs (Fig. 1, Introduction; three of the seven
pairs of the external reference library), the six-channel annotation contract
(Fig. 2, Data Resources), the corpus/QC/library overview (Fig. 3, Data
Resources), and one figure per research question (Figs. 4--7). Table 1
summarizes the data cohorts and their label status. Frozen source filenames keep their pre-2026-09-02 numbering:
`figures/figure3_channel_definition.*` is manuscript Fig. 2 and
`figures/figure2_dataset_overview.*` is manuscript Fig. 3. The new
`figures/revision/figure2_channel_definition.*` and
`figures/revision/figure3_dataset_overview.*` use the manuscript numbering.
The legacy provenance manifest uses the frozen file names; each revision
has a separate provenance record. Supplementary
tables live only in `tables/supplementary_*.tex`. The supplementary PDF
contains the full perturbation statistics (S1), the perturbation-level
alignment ablation (S2), the inactive-channel audit (S3), the cross-reference test (S4), the ASDS
candidate search (Note S5), and the integrity hashes of the frozen artifacts
(Note S6). The abstract is structured (Purpose / Methods / Results / Conclusion) and
stays within the 250-word limit, with six keywords. The
build is checked for fatal errors, undefined citations, undefined references,
overfull boxes, figure clipping, figure/table first-reference order, and the
20-page limit (see the page count recorded in `SUBMISSION_CHECKLIST.md`).
Third-party reference images come from the Calli-Tongji open subset
(ModelScope, CC BY-NC 4.0) and are attributed with the dataset citation in
every caption that shows them; the declarations use the Springer headings
(Statements and Declarations: Funding, Competing Interests, Ethics Approval,
Informed Consent, Data Availability, Code Availability, Author
Contributions).

## Provenance

`supplementary/PROVENANCE.md` lists the formal artifacts allowed to support the
paper. Synthetic smoke outputs and self-comparison demonstrations are excluded
from scientific claims.
