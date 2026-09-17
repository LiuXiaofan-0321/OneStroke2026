# Submission snapshot 2026-09-17

Submission-ready build of the IJDAR manuscript, prepared for the
2026-09-20 special-issue deadline.

## Files

| File | Pages | SHA-256 |
| --- | --- | --- |
| `OneStroke2026_manuscript_submission.pdf` | 20 | `c52f1f5a5347587823c0b22e4872ff01ae4d5c96a9d0196a24c5209209e3e1c0` |
| `OneStroke2026_ESM_1_submission.pdf` | 4 | `46ffd225c07bbdc0185a5216e3bc1eacd8e807414988e1563b5f4ba7b9f53165` |
| `OneStroke2026_online_latex_submission.zip` | 108 entries | `304495574f0fbe6a09cb919cb662255c93e38fd301a2e2cfa036785acbf0b8ca` |

The zip is a self-contained LaTeX source package (`manuscript.tex`,
`ESM_1.tex`, `sn-jnl.cls`, `sn-basic.bst`, `references.bib`, `sections/`,
`tables/`, and `figures/`) and can be imported into an online editor.

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
4. **Figure 3 explanatory text.** Panel (a) now carries the note
   "Semantic audit; exclusions frozen before any evaluation", panel (b)
   identifies itself as the training and evaluation corpus, and panel (c)
   is labelled as a separate external library. A short paragraph was added
   to Sect. 3.2 that reads the three panels explicitly, so the figure is
   interpretable without the caption. No sample pixels, counts, or panel
   contents were changed; the builder re-verified all 54 embedded images
   against their source hashes.
5. **Whitespace and length.** Float and caption separation was tightened
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
