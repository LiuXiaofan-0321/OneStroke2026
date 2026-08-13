# Alignment Ablation Protocol

## Scientific question

The benchmark tests why OneStroke uses constrained global alignment instead of
no alignment or a wider similarity-transform search. It does not modify the
production scoring implementation.

## Pre-registered variants

1. `no_alignment`: identity transform only.
2. `current_constrained`: production translation, isotropic scale `0.80-1.20`,
   and rotation `+-3 degrees`.
3. `wide_similarity`: benchmark-only translation, isotropic scale `0.60-1.40`,
   and rotation `+-12 degrees`.

The wide variant remains a similarity transform. It does not use affine,
nonuniform, or deformable warping. These ranges are fixed before formal
real-cache results are inspected.

## Error masking ratio

```text
(no_alignment_structural_drop - variant_structural_drop)
/ max(abs(no_alignment_structural_drop), 1e-8)
```

A positive value means alignment hid part of the structural-error penalty.
A negative value means alignment amplified the penalty. Values are not clipped.
Observations with effectively zero no-alignment drop have no defined ratio.

## Formal command

```bash
python -m onestroke_model.scripts.run_alignment_ablation \
  --cache-index references/cache/segformer_b2_v1/index.json \
  --output-dir artifacts/paper_ijdar/alignment_ablation
```

When the approved real cache is unavailable, the command writes the fixed
configuration and a blocking report without generating synthetic paper numbers.

## Synthetic implementation smoke

```bash
python -m onestroke_model.scripts.run_alignment_ablation \
  --synthetic-smoke \
  --output-dir artifacts/paper_ijdar/alignment_ablation_synthetic_smoke
```

Synthetic outputs validate code behavior only and must not be cited as formal
paper results.
