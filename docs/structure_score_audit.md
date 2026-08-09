# Structure Score Audit v1

## Purpose

The current OneStroke scalar is a deterministic **reference-structure agreement**
score, not a calibrated calligraphy or aesthetic grade:

```text
S_v1 = 100 * (
    0.55 * direction_macro_dice
  + 0.25 * ink_iou
  + 0.20 * keypoint_tolerant_f1_r3
)
```

This audit asks whether the aggregation itself has avoidable mathematical or
measurement artifacts before any expert-rating calibration is attempted.

The audit does **not** modify `style_scoring.py` and does not change the website
score. It is deliberately a research-side comparison.

## Audit dimensions

### 1. Both-empty direction channels receive perfect Dice in v1

The production Dice helper returns 1 when both masks are empty. That is a
defensible per-channel convention when semantic absence itself counts as a correct
negative. The audit concern is narrower: averaging those perfect empty channels
with active channels can **dilute errors in the directions that actually occur**,
and can make scores less comparable across characters with different direction
coverage.

Example: if only one direction channel is active and its Dice is 0.667, while the
other four channels are empty on both sides, the five-channel macro Dice becomes
0.933 rather than 0.667.

The audit therefore exports both:

- `direction_macro_all`: exact current semantics;
- `direction_macro_active`: average over channels where either side has pixels.

If a reference channel exists but the user entirely misses it, it remains active
and receives Dice 0. Only channels that are absent on **both** sides are omitted.

### 2. Both-empty keypoints receive F1=1 in v1

The current tolerant F1 returns 1 when both keypoint masks are empty. The audit
keeps that value for exact v1 reproduction, but separately records whether
keypoint evidence exists at all.

A coverage-aware candidate tests the alternative convention that both-empty
keypoints are **unavailable evidence**, not a perfect observed match. The keypoint
weight is omitted and the remaining configured weights are renormalized.

This is deliberately a candidate rather than a declared correction. If the
annotation protocol guarantees that "no keypoint" is an exhaustively labeled,
semantically meaningful negative, then v1's empty-empty F1=1 can be justified.
One-sided keypoint presence remains a real mismatch with F1=0 under either
convention.

### 3. Ink IoU has a double role

The current alignment search chooses the allowed global transform that maximizes
whole-ink IoU. After alignment, the same whole-ink IoU is then assigned 25% of the
final scalar.

This is not automatically wrong: ink IoU can contain useful silhouette evidence.
But it means `ink_iou` is not independent of either the alignment optimization or
the five direction masks from which the ink union is derived. The audit therefore
quantifies:

- exact equality between final `ink_iou` and the selected alignment objective;
- empirical loss correlation between direction Dice and ink IoU;
- perturbation sensitivity of each component;
- score behavior if ink IoU is retained only as an alignment/diagnostic quantity.

### 4. Equal direction-channel weighting is a semantic choice

The current direction macro gives each of the five semantic direction channels
equal weight, regardless of pixel area. This can be desirable because a small
hook or short stroke may be structurally important; conversely, a tiny noisy
channel can influence the macro as much as a large main stroke.

The audit therefore records source-reference pixel counts for all five direction
channels and the active-channel max/min area ratio. It does **not** silently
replace the macro with area weighting. Whether semantic-equal or area-aware
weighting better matches human structural judgment belongs in the later expert
calibration experiment.

### 5. Layout feedback and aligned-shape score have different semantics

Production scoring intentionally aligns translation, isotropic scale and a small
rotation before computing overlap. Meanwhile the feedback layer can still report
pre-alignment center and size differences. Therefore a high scalar can coexist
with a layout warning.

For the paper/product, this should be described as an explicit decomposition:

- post-alignment scalar: nuisance-normalized local/shape agreement;
- pre-alignment evidence: layout/placement diagnostics.

Do not claim that the current scalar itself measures every aspect of overall
layout quality unless a future calibrated score explicitly adds those terms.

## Score variants

### `v1_current`

Exact production aggregation. This is the immutable baseline for the audit.

### `v1_coverage_corrected`

Keeps the original three evidence families and the original 0.55/0.25/0.20
configured weights, with two coverage fixes:

1. both-empty direction channels are excluded from the direction macro;
2. a both-empty keypoint channel is treated as unavailable evidence rather than
   F1=1, and available weights are renormalized.

This is the lowest-risk **alternative to test** because it does not invent new
relative weights. It only changes what counts as observed evidence. Promotion
still requires checking the annotation ontology and real-cache prevalence; true
semantic absence must not be silently reclassified as "missing."

### `v2_nonredundant_candidate`

Applies the same coverage rules, then removes ink IoU from the final scalar while
keeping it for alignment and diagnostics. The original direction:keypoint prior
ratio 0.55:0.20 is preserved and renormalized over available evidence.

This is intentionally labeled a **candidate**. It must not replace production just
because one synthetic diagnostic looks favorable.

## Keypoint tolerance profile

In addition to the current 3 px tolerant F1, the audit exports F1 at radii:

```text
0, 1, 3, 5 px
```

This is descriptive only. The production score continues to use radius 3. The
profile exposes whether apparent keypoint agreement is mostly caused by the
selected tolerance radius.

The reference audit also exports the 3 px radius as a fraction of the reference
ink bounding-box diagonal. A fixed pixel tolerance is easiest to justify when
that fraction is reasonably stable across reference styles/characters; a wide
range would be evidence to test a scale-normalized tolerance in a later,
independently validated candidate.

The audit additionally computes an exact one-to-one **connected-component-center
F1** at 3 px and 5 px. This is not used in any scalar candidate yet. It exists
because the released model card describes keypoint connected-component center
coordinates as a downstream representation and recommends a small location
tolerance. If pixel-region F1 and center-matching F1 differ materially on real
references/users, that becomes a concrete candidate for the expert-calibration
stage rather than an ad-hoc metric swap.

## Weight sensitivity audit

The audit sweeps all non-negative `(direction, ink, keypoint)` weight triples on a
0.05 simplex grid (231 combinations) while keeping current component semantics.

This is **not a weight optimizer**. Its purpose is to demonstrate how easy it is to
change aggregate perturbation metrics by changing weights. The controlled
perturbation suite contains a deliberate mixture of direction, width, nuisance and
keypoint errors; therefore optimizing a scalar on that same mixture would tune to
our chosen benchmark composition.

Do not choose a new weight triple from `weight_sensitivity_grid.csv` and then quote
the same perturbation experiment as independent validation.

Final user-facing weight calibration requires an independent target, preferably
blinded human structural-similarity ratings.

## Inputs

Formal runs consume the existing approved reference cache:

```text
references/cache/segformer_b2_v1/index.json
```

No reference assets need to be committed to Git.

## Outputs

```text
score_audit_results.csv          # all atomic evidence + all score variants
reference_coverage.csv           # inactive direction / keypoint availability by reference
component_correlation.csv        # correlation of component losses
keypoint_metric_comparison.csv   # tolerant pixel F1 vs component-center F1
component_sensitivity.csv        # max-severity sensitivity by perturbation
score_variant_correlation.csv    # rank/value agreement among score variants
score_variant_behavior.csv       # nuisance + monotonicity behavior by variant
score_variant_overall.csv        # compact macro-over-perturbation comparison
score_variant_overall_by_style.csv
reference_coverage_by_style.csv
weight_sensitivity_grid.csv      # 231 diagnostic weight triples; NOT a tuning result
structure_score_audit_report.json
structure_score_audit_report.md
```

The raw CSV includes all five direction-channel Dice values and the selected
alignment transform so aggregate findings can be traced back to individual cases.

## Commands

### Tests

```bash
pytest -q \
  tests/test_controlled_perturbations.py \
  tests/test_perturbation_benchmark.py \
  tests/test_structure_score_audit.py \
  tests/test_structure_score_audit_benchmark.py
```

### Synthetic implementation smoke

```bash
python -m onestroke_model.scripts.run_structure_score_audit \
  --synthetic-smoke \
  --output-dir artifacts/structure_score_audit_synthetic
```

Synthetic numbers are implementation validation only and must not appear as paper
results.

### Formal full-reference audit

```bash
python -m onestroke_model.scripts.run_structure_score_audit \
  --cache-index references/cache/segformer_b2_v1/index.json \
  --output-dir artifacts/paper/structure_score_audit_v1
```

Do not use `--limit-per-style` for the final paper audit.

## Decision gates

1. **Production parity:** recomputed `v1_current` must match the production-reported
   score to numerical tolerance.
2. **Coverage semantics + prevalence:** only consider promoting
   `v1_coverage_corrected` after verifying what an absent direction/keypoint means in
   the annotation ontology and measuring how often real references/users expose that
   condition.
3. **Redundancy:** high direction/ink correlation is a warning, not sufficient reason
   to delete ink IoU.
4. **Controlled behavior:** any candidate must retain nuisance robustness and
   non-increasing response to increasing structural severity.
5. **Independent calibration:** final scalar choice/weights require expert structural
   ratings or another independent external target. The controlled perturbation suite
   must not serve simultaneously as tuning and headline validation data.
