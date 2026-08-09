# Controlled Perturbation Benchmark v1

## Scope

This benchmark audits the deterministic **reference alignment + structural scoring**
contract used by OneStroke. It deliberately operates on cached six-channel binary
masks rather than source images. Therefore it answers:

> Does the current scoring pipeline ignore allowed global nuisance variation while
> responding consistently to controlled structural changes?

It does **not** measure SegFormer robustness. Image-level perturbations belong in a
separate perception robustness experiment.

The benchmark does not change `style_scoring.py`. It uses a benchmark-only
`PreparedReferenceScorer` that preserves the production 9 x 7 scale/rotation grid,
centroid-derived translation, direction-ink IoU objective, score formula, and
first-win tie behavior. Unit tests compare it directly against production
`score_masks`.

## Input contract

Formal paper runs use the existing local cache index:

```text
references/cache/segformer_b2_v1/index.json
```

Each reference cache must contain `binary_masks` with shape `[H, W, 6]` and the exact
channel order:

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

The repository intentionally does not need to redistribute reference cache files for
this benchmark. The run report records cache-index SHA-256, checkpoint SHA-256,
Python/NumPy/Pillow versions, Git commit when available, and SHA-256 hashes of the two
benchmark implementation modules.

## Perturbation families

### Nuisance / expected invariant

1. `global_translation`: 4, 8, 12, 16 px.
2. `global_rotation`: 0.5, 1.5, 2.5 degrees.
3. `global_scale_up`: +2.5%, +7.5%, +12.5%, +17.5%.
4. `global_scale_down`: -2.5%, -7.5%, -12.5%, -17.5%.
5. `compound_allowed_transform`: three increasing combinations of permitted scale,
   rotation, and translation.

Rotation, scale, and compound levels are intentionally **off the production search
grid**. Exact on-grid recovery would mainly test that the same transform can be
inverted by the same discrete grid. Off-grid values instead audit discretization and
nearest-neighbor rasterization behavior inside the already permitted transform range.

Before rotation/scale/compound perturbations are scored, a conservative transformed
foreground-bounding-box check is applied. If the requested transform risks moving
foreground outside the canonical canvas, the observation is retained as `invalid`
with an explicit reason. Crop loss is therefore not silently interpreted as failure
of nuisance invariance.

### Structural / expected decreasing

1. `direction_terminal_deletion`: remove 5%, 10%, 20%, 30% of a nested terminal
   fragment from one direction channel. Nearby keypoint pixels are removed as part of
   the same physical deletion.
2. `extra_direction_fragment`: add an offset duplicate of a nested terminal fragment
   at 5%, 10%, 20%, 30% of the selected direction region.
3. `local_fragment_shift`: move a fixed 20% terminal fragment by 4, 8, 12, 16 px
   perpendicular to its dominant axis; spatially associated keypoints move with it.
4. `direction_width_dilate`: dilate one direction channel by radius 1, 2, 4, 6 px.
5. `direction_width_erode`: erode one direction channel by radius 1, 2, 3, 4 px.
6. `keypoint_shift`: move only the keypoint channel by 2, 4, 8, 12 px, explicitly
   auditing the scorer's 3 px tolerant keypoint F1.

A local structural target direction is selected by a stable SHA-256 rule among
eligible non-empty channels. The same reference therefore receives the same target
channel at every severity, and selection never consults score outcomes or model
errors.

## Statistics

### Identity sanity

Every reference is scored against itself. The expected score is exactly 100. Any
identity deviation is a benchmark failure and is reported.

### Nuisance invariance

For each nuisance observation:

```text
absolute score drop = |identity score - perturbed score|
```

The report includes mean, median, p95, maximum drop, valid fraction, and the fractions
retaining scores at least 99 and at least 95.

### Structural monotonicity

For each structural perturbation, complete per-reference severity curves are used for:

- Spearman correlation between severity and score;
- maximum-severity score drop;
- normalized drop area under the severity curve.

In addition, adjacent configured severity pairs are checked for:

- non-increasing score;
- strict score decrease.

If a severity is invalid, the benchmark does not bridge across the missing level and
pretend the remaining two observations are adjacent. Invalid rows remain in the raw
CSV and are reported separately.

### Descriptive family separation

The report also gives a compact comparison between nuisance and structural score drop
at the preregistered maximum severity of each perturbation. This is **descriptive
only**: pixels, degrees, fractions, and morphology radii are not commensurate severity
units, so this number must not be presented as a matched effect-size or significance
test.

### Severity summary

Each severity reports mean, sample standard deviation, median, p05, p95, plus a
nonparametric percentile bootstrap 95% CI for mean score and mean score drop. Bootstrap
resampling uses 2,000 reference-level draws with a deterministic SHA-256-derived RNG
seed.

### Style-stratified summary

The same score/drop curves are exported per `style_id` so that one reference pack
cannot silently dominate the aggregate behavior.

## Output files

A formal run writes:

```text
perturbation_results.csv          # every reference x perturbation x severity row
baseline_identity.csv             # identity sanity rows
perturbation_summary.csv          # aggregate severity curves + bootstrap CI
style_perturbation_summary.csv    # style-stratified severity curves
behavior_summary.csv              # per-family invariance/monotonicity audit
benchmark_report.json             # machine-readable protocol + provenance + audit
benchmark_report.md               # compact human-readable review report
```

`perturbation_results.csv` includes the selected alignment transform and serialized
perturbation metadata so individual failures can be traced without rerunning the
experiment.

## Commands

### Unit tests

```bash
pytest -q tests/test_controlled_perturbations.py tests/test_perturbation_benchmark.py
```

### Synthetic smoke test

This requires no model checkpoint, GPU, licensed reference images, or reference cache:

```bash
python -m onestroke_model.scripts.run_controlled_perturbation_benchmark \
  --synthetic-smoke \
  --output-dir artifacts/controlled_perturbation_synthetic_smoke
```

Synthetic smoke results are implementation validation only and must **not** be quoted
as paper results.

### Formal full-reference run

Run from the repository root after the approved reference cache already exists:

```bash
python -m onestroke_model.scripts.run_controlled_perturbation_benchmark \
  --cache-index references/cache/segformer_b2_v1/index.json \
  --output-dir artifacts/paper/controlled_perturbation_v1
```

No `--limit-per-style` should be used for the final paper run.

For a quick local real-reference dry run only:

```bash
python -m onestroke_model.scripts.run_controlled_perturbation_benchmark \
  --cache-index references/cache/segformer_b2_v1/index.json \
  --limit-per-style 2 \
  --output-dir artifacts/controlled_perturbation_real_smoke
```

When a limit is requested, references are selected by a stable SHA-256 ordering within
style, never by score or visual difficulty.

## Interpretation rules for the paper

Do not write that nuisance transformations are “perfectly invariant” unless the formal
real-reference data supports it. The current production alignment is a discrete
optimizer with nearest-neighbor mask rasterization, so a small off-grid nuisance drop
is expected and is itself an informative calibration result.

Do not call the output an aesthetic grade. The benchmark only validates the current
prototype **structural agreement score**.

Do not hide invalid perturbations. Report the invalid fraction and reasons; if clipping
risk is concentrated in a style pack or perturbation severity, discuss it explicitly.

Do not use the synthetic smoke numbers in the manuscript. Formal conclusions must be
computed from the approved local reference cache.
