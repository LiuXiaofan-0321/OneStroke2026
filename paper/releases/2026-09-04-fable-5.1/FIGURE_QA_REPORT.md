# Figure QA report: Nature-level redesign of Figures 1–7

Status date: 2026-09-03. Applies to `paper/figures/redrawn/*.pdf` as included in
`paper/manuscript.pdf` (branch `claude/onestroke-paper-restructure-wnaphp`).

## Scope and ground rules

- Every glyph, mask, and overlay tile is recovered pixel-exactly from the frozen
  renders in `paper/figures/figure{1..7}_*.png`; no data, prediction, ground
  truth, or example was changed or re-selected. Only colour mapping of flat
  overlay regions (purple overlap → dark neutral), typography, layout, legends,
  call-outs, and native data plots are new.
- Every printed number is traceable: `figure_provenance_manifest.json`
  (Figs. 1, 3, 5, 6, 7 values), `artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_pairs.csv`
  (Fig. 6g scatter), `tables/segmentation_results.tex` (Fig. 4 dataset-level
  character-disjoint Macro Dice), `tables/feedback_failure_taxonomy.tex`
  (Fig. 7 taxonomy strip). The per-figure provenance lists are in the workflow
  transcripts and were re-checked by an independent science-fidelity reviewer.
- Each figure went through draw → two independent reviews (science fidelity,
  information design) → fix → post-fix verification. Blocking findings that
  were raised and resolved: Fig. 1 inset semantics (it is the bounding box of
  the multi-label pixels at reduced scale, not a zoom; caption corrected);
  Fig. 4 an unsourced per-sample model ranking in a call-out (removed);
  Fig. 5 grayscale missing-vs-extra ambiguity and a stale caption (dashed/solid
  outlines added, caption rewritten); Fig. 6 swapped candidate/reference glyphs
  and a heading that implied the annotated-mask-union ASDS is a parser output
  (both corrected); Fig. 7 an arithmetically impossible cohort statement, a
  digit-adjacent label ("top 3 718"), and a predicted-cell cue invisible in
  grayscale (all corrected).

## Design system (all figures)

| Element | Rule |
|---|---|
| Font | Latin Modern Sans (TrueType, embedded), 7 pt base, nothing below 6 pt |
| Panel labels | bold lowercase letter + short heading, one weight |
| Rules and frames | 0.5 pt light grey (`#D0D6DC`); no boxes, shadows, or gradients |
| Legend | one unframed chip row per figure with non-colour cues |
| vec1–vec5 | `#D62728` `#009E73` `#0072B2` `#E69F00` `#7B4AB5`, unchanged; chips carry stroke-direction icons |
| Simultaneous labels | black |
| Overlap (matched ink) | dark neutral `#4B5057` (purple is now vec5-only) |
| Missing reference ink | blue `#0072B2`, dashed outline / hatch |
| Extra candidate ink | red `#D62728`, solid outline / counter-hatch |
| Endpoint channel | cyan `#00A6D6`, hollow-square / circle cue |

## Per-figure QA

| Fig. | File stem | Size (in) | Page | Height cap | Visual centre | Grayscale check |
|---|---|---|---|---|---|---|
| 1 | figure1_pipeline | 6.30 × 1.90 | 3 | 1.95 | stage track: Input pair → Overlapping parse → Bounded registration → Spatial evidence → Structured output; one score line vs seven evidence rows | pass: hatch separates missing/extra; direction icons in legend |
| 2 | figure3_channel_definition | 6.34 × 2.87 | 6 | 2.90 | enlarged crossing (e) with "one pixel, two or more labels" pointer | pass: direction icons; black multi-label pixels |
| 3 | figure2_dataset_overview | 6.30 × 4.61 (placed at 0.92 width) | 7 | 4.90 | proportional QC funnel 894 → 840 → (−12, −59) → 769 | pass: counts carry the message |
| 4 | figure4_segmentation_qualitative | 6.34 × 3.49 | 12 | 3.50 | call-outs on crossing, endpoints, held-out errors; dataset-level Dice line | pass (in-tile channel hues collapse, as in the original; legend icons compensate) |
| 5 | figure5_alignment_ablation | 6.15 × 3.07 | 14 | 3.20 | score-drop chart: drops collapse in (a)–(b), remain in (c) | pass: dashed/solid outlines; marker shapes |
| 6 | figure6_asds_direct_ink | 6.28 × 2.95 | 16 | 3.10 | silhouette → descriptors → 83.1 → human agreement; direct-ink control strip | pass with a documented limit: candidate/reference profile curves in (e) are colour-only (rows/columns stay solid/dashed) |
| 7 | figure7_diagnostic_cases | 6.29 × 2.82 | 16 | 2.90 | verdict cards (✓ correct / ✗ failed) and the failure-taxonomy strip | pass: black solid/dashed cell frames; neutral taxonomy ramp |

Height caps were set so that the manuscript stays inside the 20-page limit.

## Page count

| Version | Main manuscript | Online Resource 1 |
|---|---|---|
| Before this revision (frozen originals, 2026-09-02) | 20 pages | 4 pages |
| Previous redraw (2026-09-03 a.m.) | 20 pages | 4 pages |
| This redesign, with structured abstract and Springer declarations | 20 pages | 4 pages |

The build gate (no undefined references or citations, no overfull boxes) passes;
figures are numbered in first-reference order and each float appears on or after
the page of its first reference.

## Deliverables in this directory

- `contact_sheet_before_after.png` / `.pdf`: frozen original | previous redraw | new redesign, one row per figure.
- `<stem>_gray.png`: grayscale (luminance) version of each figure.
- `<stem>_print_preview.png`: the manuscript page carrying the figure, rendered at 150 dpi (true printed size at screen resolution).
- `<stem>_print_crop.png`: 1:1 crop of the figure region of that page at 300 dpi.
- `qa_metrics.json`: pixel sizes, inch sizes, page numbers, distinct-colour bins, and page counts.

Regenerate everything with `python3 paper/figures/redraw/redraw_<stem>.py` (one per figure) followed by
`python3 paper/figures/redraw/qa_report.py --previous <dir of previous PNGs>` after compiling the manuscript.

## Residual notes for the authors

- Fig. 1: the framed inset in panel (b) is inherited from the frozen render; it shows the bounding box of the multi-label pixels at reduced scale (the caption now says so). If the raw parse is ever re-rendered, drop the inset.
- Fig. 5: absolute scores are no longer printed under the tiles; they are exactly 100 minus the plotted drop (axis title says so) and remain in Table 4 / Online Resource 1.
- Fig. 7: severities are printed without a unit because no unit is recorded in the manifest or the text.
- Calli-Tongji images (Figs. 1, 3, 5) are attributed as "Calli-Tongji open subset, CC BY-NC 4.0" with the dataset citation in the captions.
