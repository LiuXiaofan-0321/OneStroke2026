# Figure 3 — revision QA

Date: 2026-09-05. Outputs: PDF, editable SVG, 600-dpi PNG, reproducible Python source, and JSON provenance. Final size: 6.30 × 4.35 in (the current manuscript's text width).

## Checks completed

- Viewed all seven original figure previews before redesign; inspected the new Figure 3 PNG after correcting the QC annotation overlap.
- All 40 existing project tiles and all 14 images of the seven external pairs are retained in their original order. No additional sample selection, crop, intensity adjustment, thresholding, or model run was performed.
- All 54 native RGB image hashes match the source PDF after accounting for the PDF backend's internal reversed row storage and compensating page transform. No visual image reflection is introduced.
- Character labels were checked against the repository's character map and the source PDF text. Sample IDs and pair IDs are retained in the JSON provenance record.
- The original PDF's embedded Chinese font subset is extracted by the build script. It is embedded in the new PDF and in the SVG; all character labels remain selectable in PDF text extraction. The script regenerates the temporary font even if the `qa` folder is omitted from a delivery package.
- The explicit audit counts reconcile: 894 − 54 = 840; 840 − 12 − 59 = 769. The two exclusion sets are described as in the manuscript. No count or split is recomputed.
- The current raster preview has no title collision, cropped labels, or overlap between the `Complete GT` state and exclusion descriptions.
- Source validator: 12 PASS, 2 WARN, 0 FAIL. The two warnings are deliberate: the requested delivery uses PNG preview plus vector PDF/SVG rather than TIFF; the width is 160.02 mm to match the current 6.3-in manuscript text width rather than a generic 89/183-mm preset.

## Replacement caption

Data resources and quality control. (a) Recovery and exclusion audit: of 894 recovered samples, 54 lack the character-specific direction mapping, leaving 840 with complete six-channel ground truth; removal of 12 image/GT mismatches and 59 non-canonical exact duplicates yields 769 QC-clean observations of 40 identities. No exact-duplicate group crosses either frozen split. (b) One deterministic QC-clean observation per identity (IDs 0–39), retaining the previously selected examples. (c) All seven natural same-character cross-style pairs supported by the 200-image external reference library, with Ouyang Xun regular script above Wang Xizhi running script. These are cached masks from the frozen v1 parser, not segmentation ground truth. Source images: Calli-Tongji open subset, CC BY-NC 4.0.

Retain the existing citation to `yunmo_jixin_2025` after the source name in the manuscript caption.

## Required manuscript reference updates

- `figures/redrawn/figure2_dataset_overview.pdf` → `figures/revision/figure3_dataset_overview.pdf`.
- Keep the stable LaTeX label `fig:data-resources`.
- Old panel reference `Fig. ... e,f` → `Fig. ... a,b` in the quality-control paragraph.
- Old panel reference `Fig. ... g` → `Fig. ... c` in the cross-reference cohort paragraph.
- The former repeated acquisition panels a–d have been removed from this figure; their information remains in the preceding channel-definition figure. The replacement caption must therefore replace the original caption completely.

## Limits

This is a faithful recomposition of the published figure assets available in the checkout. The original dataset is not present here; the provenance verifies identity to the frozen figure's native embedded images, not an independent audit against raw acquisition files. Native image resolution is preserved and recorded per tile in JSON; a high-dpi preview does not create new image detail.
