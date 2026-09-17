# Submission snapshot 2026-09-17

Submission-ready build of the IJDAR manuscript, prepared for the
2026-09-20 special-issue deadline.

## Files

| File | Pages | SHA-256 |
| --- | --- | --- |
| `OneStroke2026_manuscript_submission.pdf` | 20 | `fd96ca271a5e9932f4142973bec70a15fc32ed81c09fedfc58565e1650bf2003` |
| `OneStroke2026_ESM_1_submission.pdf` | 4 | `c7382f515c01aeecfe0c1de2a20ffd10d6b81a9dc15f747a3f0c036b30d16267` |
| `OneStroke2026_online_latex_submission.zip` | 102 entries | `2b794200958ef8f8db50702c38433985691ca0f330981e71e2559ec99a9c4f80` |

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
2. **Figure 3 explanatory text.** Panel (a) now carries the note
   "Semantic audit; exclusions frozen before any evaluation", panel (b)
   identifies itself as the training and evaluation corpus, and panel (c)
   is labelled as a separate external library. A short paragraph was added
   to Sect. 3.2 that reads the three panels explicitly, so the figure is
   interpretable without the caption. No sample pixels, counts, or panel
   contents were changed; the builder re-verified all 54 embedded images
   against their source hashes.
3. **Whitespace and length.** Float and caption separation was tightened
   (`\textfloatsep`/`\dbltextfloatsep` 9 pt, `\floatsep`/`\dblfloatsep`
   11 pt, `\abovecaptionskip` 2 pt, `\belowcaptionskip` 4 pt) so that the
   two added passages fit without pushing the manuscript past the 20-page
   limit. No text was deleted to make room.

## Build verification

- `pdflatex` + `bibtex` + `pdflatex` + `pdflatex`: 20 pages, no undefined
  references or citations.
- Zero `Overfull` boxes in `manuscript.log` and `ESM_1.log`.
- Last text block of the final page ends at 672 pt of 842 pt, i.e. the
  document fills the page without trailing blank space.
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
