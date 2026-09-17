# Figure 6 verification

The revised figure explains the frozen ASDS components above the direct-ink control. It preserves the original a–f mechanism panels and puts all three cohort scatter plots within panel g. Its interpretation is closely matched observed associations on the retrospective clean direct-digital cohort; it does not introduce an equivalence test or external-validation claim.

- Physical size: 6.30 × 3.08 inches, matching the manuscript text width. Labels use Liberation Sans, 6.5–8 pt; the single ASDS value is a 12 pt callout.
- Editable PDF and SVG contain native text, heatmap cells, colorbars, and projection curves. The three source example images retain their original pixels apart from blank-margin cropping of the raw glyphs.
- PNG and LZW-compressed TIFF are exported at 600 dpi.
- Source preflight passes all failure gates. The sole retained warning is the deliberately chosen 160 mm manuscript width rather than generic 89/183 mm defaults.
- All 150 source observations across 40 characters are shown in each of the three scatter plots. There is no sampling, exclusion, jitter, or fitted regression line. The example follows the original deterministic median-difference selection rule.
- Recomputed Spearman associations are 0.5562290124897076, 0.5558310017217053, and 0.9973225476687853; all agree exactly with the frozen report. The character-cluster bootstrap intervals remain unchanged.
- The legacy `parsed_asds_score` CSV column is correctly labelled annotated-mask-union ASDS, not a parser prediction. No raw masks are reconstructed.
- Heatmap cell colors are copied from the frozen PDF and rendered as native vector cells. The 0–1 display key denotes each map's absolute occupancy differences scaled by its own maximum, consistent with the original renderer. Absolute occupancy maxima are unavailable and are not invented; comparisons of magnitude between the polar and grid maps are unsupported.
- The original native vector projection paths are reused with one common affine y mapping. All four profiles are vertically rescaled together for display, preserving their relative amplitudes; no raw probability magnitudes are inferred.
- Rendered PNG and native PDF were inspected for legibility, clipping, and overlap. All text lies within the canvas, and the final revision has no caption/footer collision.

The manuscript caption should define the within-panel map normalization; state that profile heights use a common display scale; identify the brackets as character-cluster 95% confidence intervals; define the paired difference as annotated-mask-union minus direct-ink association; and identify the filled example marker and right-panel identity line.

Source and export hashes, the complete source-field mapping, illustrative tile locations, exact observation counts, and selection provenance are in `figure6_asds_direct_ink.json`. Rebuild with `python paper/figures/revision/build_figure6.py` from the repository root, or invoke the script by its absolute path.
