# Figure 1 — revision QA

Date: 2026-09-17. Outputs: vector PDF, 600-dpi PNG, reproducible Python source,
and JSON provenance. Final size: 6.295 × 1.903 in, unchanged from the frozen
figure, so the manuscript page budget is unaffected.

## What changed

Panel (a) previously showed a single same-character cross-style pair. It now
shows three pairs from the frozen external reference library, arranged with the
target character as the row and the style role as the column:

```text
              reference   candidate
  亮 (row 1)   Ouyang Xun  Wang Xizhi   <- frozen pair, tiles reused unchanged
  息 (row 2)   Ouyang Xun  Wang Xizhi
  尉 (row 3)   Ouyang Xun  Wang Xizhi
```

Selection rule: the frozen pipeline pair (target character 亮) followed by the
next pairs in the frozen `cross_reference_pairs.csv` order. No pair was chosen
by visual preference, and the three pairs are a subset of the seven already
shown in manuscript Figure 3, panel (c).

Panel (a) also adopts the plate treatment of the rest of the figure, so the
input card no longer reads as a bare white cut-out beside the framed cards of
panels (b)--(e):

```text
tile paper            white        ->  247, 248, 250  (PANEL_BG card grey)
tile outline          none         ->  hairline, 0.55 pt, 215, 220, 225 (GRID)
stage-label strip     white pill   ->  continuous 238, 240, 242 grey
```

The tile papers are mapped by one uniform linear function per channel,
``out = round(C * plate / 255)``, which sends white paper exactly to the plate
colour and leaves black ink fixed. No contrast, gamma, threshold, crop, or
resampling operation is applied. Because the mapping is linear and ink is
anchored at zero, the ink density relative to the paper,
``(paper - min(RGB)) / paper``, is preserved; the build asserts this and
records the maximum deviation per tile (2.1e-3, i.e. within one 8-bit level).

Panels (b)--(e) and the shared direction legend are the frozen vector artwork,
carried over as PDF content rather than re-rendered as raster: the original
page is placed, panel (a) is removed with a PDF redaction, and only the gallery,
its labels, and the strip repair are added. Type, hairlines, and colours of the
pipeline panels are therefore byte-for-byte the published ones.

## Checks completed

- Every part of the page outside panel (a) and the strip repair is rasterised
  at 600 dpi and compared with the frozen figure: 0 pixels differ for
  x ≥ 74 pt and for y ≤ 106 pt; the only differences on the page fall in
  x 4.6--72.4 pt and y 4.9--121 pt, i.e. panel (a), its recentred title, and the
  strip segment the redaction had cleared.
- Row 1 reuses the two frozen embedded tiles (the previous figure's 亮 pair) as
  its ink source, so the pair already discussed in the text carries the same
  ink; only its paper colour changes. Rows 2 and 3 use the matching 256 × 256
  source images of the reference cache, reduced to 194 × 194 with the same
  Lanczos rule already applied to the frozen tiles.
- The superseded panel-(a) tiles are removed by redaction rather than covered,
  so the page carries no hidden duplicate images. Verified: the rebuilt page
  contains exactly four images from the frozen artwork plus the six gallery
  tiles.
- The input card is now visually continuous with the rest of the figure: each
  tile sits on the card grey inside a GRID hairline of the same width as the
  window spines of panels (b)--(d), and the stage-label strip runs unbroken
  across the panel-(a) column instead of stopping at a white pill. Measured on
  the rebuilt page: tile plate 247/248/250, frame 215/220/225, strip
  238/240/242 under the "Input pair" label.
- Labels keep the frozen wording ("reference", "candidate", "Input pair"),
  size, and colour. They are re-drawn with the source PDF's own embedded font
  subsets (LMSansTT8-Regular, LMSansTT10-Bold), extracted by the build script;
  character labels use Microsoft YaHei for CJK coverage. All injected text is
  vector and remains selectable.
- All embedded fonts are subset to the glyphs actually used before saving, so
  the delivered figure is 371 kB rather than megabytes; the character labels
  still extract and render correctly afterwards.
- The "Input pair" title was recentred under the widened panel so that it stays
  centred beneath its panel, as in the frozen layout.
- Page size, text layer, and the shared legend row were re-checked after the
  rebuild; the manuscript still compiles to 20 pages with no overfull boxes.
- No model inference, rescoring, thresholding, or new data selection is
  performed. All numerical values printed in panel (e) come from the frozen
  figure.

## Limits

This is a faithful recomposition of published figure assets in the checkout.
Tiles are verified against the frozen figure and the reference cache, not
against a re-run of the parser. The three displayed pairs are illustrative of
cross-style variation; they are not the natural same-character, different
instance pairs used in the human study.
