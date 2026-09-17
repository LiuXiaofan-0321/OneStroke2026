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

Panels (b)--(e) and the shared direction legend are the frozen vector artwork,
carried over as PDF content rather than re-rendered as raster: the original
page is placed, panel (a) is removed with a PDF redaction, and only the gallery
and its labels are added. Type, hairlines, and colours of the pipeline panels
are therefore byte-for-byte the published ones.

## Checks completed

- Panel (b)--(e) region rasterised at 600 dpi and compared with the frozen
  figure: 0 pixels differ. All differences on the page are confined to
  x 4.6--67.7 pt and y 4.9--117.8 pt, i.e. panel (a) and its recentred title.
- Row 1 reuses the two frozen embedded tiles (the previous figure's 亮 pair) so
  the pair already discussed in the text is unchanged; rows 2 and 3 use the
  matching 256 × 256 source images of the reference cache, reduced to 194 × 194
  with the same Lanczos rule already applied to the frozen tiles.
- The superseded panel-(a) tiles are removed by redaction rather than covered,
  so the page carries no hidden duplicate images. Verified: the rebuilt page
  contains exactly four images from the frozen artwork plus the six gallery
  tiles.
- Labels keep the frozen wording ("reference", "candidate", "Input pair"),
  size, and colour. They are re-drawn with the source PDF's own embedded font
  subsets (LMSansTT8-Regular, LMSansTT10-Bold), extracted by the build script;
  character labels use Microsoft YaHei for CJK coverage. All injected text is
  vector and remains selectable.
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
