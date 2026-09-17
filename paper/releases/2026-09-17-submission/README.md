# Submission snapshot 2026-09-17

Submission-ready build of the IJDAR manuscript, prepared for the
2026-09-20 special-issue deadline.

## Files

| File | Pages | SHA-256 |
| --- | --- | --- |
| `OneStroke2026_manuscript_submission.pdf` | 20 | `8715f6cd60064145f9fcd1a70f6029656b7173ab7eaf763a011125a1fbfe3988` |
| `OneStroke2026_ESM_1_submission.pdf` | 4 | `56789a089bcf5a11154b4121ee86111e000a1ebd092e1af4a5730f5b6030f64c` |
| `OneStroke2026_cover_letter.pdf` | 2 | `5f1ad59522e8084d3d3a58ddf11c58b75527f5dae6018b0cb227e2cf0086a6f5` |
| `OneStroke2026_manuscript_latex.zip` | 33 entries | `1d22cdc97598dd777a1c977b5329cc43aa1a6253f46927aaec5bcd9f9c5a1ba7` |
| `OneStroke2026_online_latex_submission.zip` | 109 entries | `3e5cfdd53d712662ed83e406b15455d307a264e438bfc4952fe6311ac3b264c6` |

## Which file goes into which submission slot

| Submission slot | File |
| --- | --- |
| Manuscript file | `OneStroke2026_manuscript_latex.zip` (main document `manuscript.tex`) |
| Supplementary material | `OneStroke2026_ESM_1_submission.pdf` |
| Related files | `OneStroke2026_cover_letter.pdf` |
| Details / Authors / Declarations tabs | text in `DECLARATIONS.md` |

Per-slot instructions, the clean-room compile acceptance test, and the
outstanding author actions are in `SUBMISSION_UPLOAD_GUIDE.md`.
`OneStroke2026_online_latex_submission.zip` is the collaboration package for
Overleaf, not the submission package.

The zip is a self-contained LaTeX source package (`manuscript.tex`,
`ESM_1.tex`, `sn-jnl.cls`, `sn-basic.bst`, `references.bib`, `sections/`,
`tables/`, and `figures/`) and can be imported into an online editor.

## Correction applied to this snapshot (2026-09-17, second build)

7. **Affiliation name.** The affiliation was corrected from
   ``School of Software Engineering'' to ``Software Engineering Institute''
   in `manuscript.tex`, `ESM_1.tex`, and `AUTHOR_BIOGRAPHIES.md`.
8. **Author biography pronoun.** Yuan Feng's biography now uses feminine
   pronouns, consistent with the author's own account.

Nothing else changed: page counts, section order, all reported values,
figures, tables, and the reference list are identical to the first build of
this snapshot. Only the three files above were edited, and the three
artifacts were rebuilt, so the SHA-256 values in the table replace the
previous ones.

## Changes relative to the 2026-09-05 package

1. **Introduction opening.** The first paragraph now opens with the
   cultural and script-style framing requested by the authors: calligraphy
   is a foundational form of traditional Chinese culture; the seal
   (*zhuan*), clerical (*li*), regular (*kai*), running (*xing*), and
   cursive (*cao*) styles use distinct stroke techniques and carry a wide
   range of qualities; two legible instances of the same character can
   still differ in the local structure that instruction attends to. The
   existing sentence on legibility versus local structure is retained
   immediately after it, so no claim is duplicated or weakened.
2. **Abstract opening.** The Purpose sentence carries the same framing in
   condensed form (brush-written art, five script styles, two legible
   instances that still differ locally). Redundant wording elsewhere in the
   abstract was trimmed by the same number of words so the abstract stays
   inside the 150--250 word limit (228 words).
3. **Figure 1 panel (a).** Panel (a) now shows three of the seven natural
   same-character cross-style pairs instead of one, with the target character
   as the row and the style role (Ouyang Xun regular-script reference, Wang
   Xizhi running-script candidate) as the column. Row 1 is the previously
   published pair and reuses its frozen tiles unchanged; rows 2 and 3 are the
   next pairs in the frozen pair file. Panels (b)--(e) are the frozen vector
   artwork: the builder places the original page, removes the old panel (a) by
   redaction, and adds only the gallery. At 600 dpi the (b)--(e) region is
   pixel-identical to the frozen figure, and the page size is unchanged.
4. **Figure 1 plate treatment.** The input card no longer reads as a bare white
   cut-out: each tile now sits on the figure's card grey (247, 248, 250)
   inside a 0.55 pt hairline frame (215, 220, 225), matching the framed cards
   of panels (b)--(d), and the bottom stage-label strip (238, 240, 242) runs
   unbroken across the panel-(a) column. Tile papers are mapped by one uniform
   linear function that sends white paper to the plate colour and fixes black
   ink, so the ink density relative to the paper is preserved to within one
   8-bit level (maximum recorded deviation 2.1e-3); no contrast, gamma,
   threshold, or crop operation is applied.
   The strip band carrying the "Input pair -> Overlapping parse" chevron falls
   inside the redacted area, so that band is re-inserted from the frozen vector
   artwork; all four strip chevrons now match the frozen figure with 0/255
   pixel difference.
5. **Figure 3 explanatory text.** Panel (a) now carries the note
   "Semantic audit; exclusions frozen before any evaluation", panel (b)
   identifies itself as the training and evaluation corpus, and panel (c)
   is labelled as a separate external library. A short paragraph was added
   to Sect. 3.2 that reads the three panels explicitly, so the figure is
   interpretable without the caption. No sample pixels, counts, or panel
   contents were changed; the builder re-verified all 54 embedded images
   against their source hashes.
6. **Whitespace and length.** Float and caption separation was tightened
   (`\textfloatsep`/`\dbltextfloatsep` 9 pt, `\floatsep`/`\dblfloatsep`
   11 pt, `\abovecaptionskip` 2 pt, `\belowcaptionskip` 4 pt) so that the
   two added passages fit without pushing the manuscript past the 20-page
   limit. No text was deleted to make room.

## Build verification

- `pdflatex` + `bibtex` + `pdflatex` + `pdflatex`: 20 pages, abstract 228
  words, no undefined references or citations.
- Zero `Overfull` boxes in `manuscript.log` and `ESM_1.log`.
- Last text block of the final page ends at 672 pt of 842 pt, i.e. the
  document fills the page without trailing blank space.
- Figure 1 rebuilt with `figures/revision/build_figure1.py`; panels (b)--(e)
  are pixel-identical to the frozen figure at 600 dpi and the page size is
  unchanged.
- Figure 3 rebuilt with `figures/revision/build_figure3.py`; the builder
  asserts native pixel-hash equality for every embedded tile and reports
  zero text overlaps.

## Still open before submission

These are author or institution actions, not build issues:

- confirm Ethics Approval / Informed Consent wording and the
  data-availability statement;
- confirm that the CC BY-NC 4.0 Calli-Tongji reference images may be
  reproduced in a commercial publisher's article, or replace them;
- approve author biographies and supply portrait photographs.
