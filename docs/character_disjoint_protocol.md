# Character-Disjoint Generalization Protocol

The frozen split is generated without reading model predictions or test scores.
It guarantees zero `char_id` overlap across train, validation, and test.

Original frozen character assignment:

- 28 train characters / 588 samples
- 6 validation characters / 126 samples
- 6 test characters / 126 samples
- split SHA-256:
  `eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e`

Formal training applies the frozen semantic QC exclusion layer after that
assignment:

- 12 source-image/GT mismatches excluded;
- 59 exact image+mask duplicate non-canonical instances excluded;
- 769 QC-clean observations overall;
- 28/6/6 characters and 539/114/116 active train/validation/test samples;
- derived split SHA-256:
  `e9303314d1b70d3f92efcdc5c0807f833148cbe64c2702379f0ac951ed2a1e2b`;
- exclusion-list SHA-256:
  `6397ed346618173edaef1e8146ec162836046fafb35869227a13a2c4ee6cc467`.

The original six-channel GT is restored from the pinned legacy archive with:

```bash
python -m onestroke_model.scripts.restore_legacy_gt \
  --archive /path/to/OneStroke-main.tar.gz \
  --destination data/legacy_gt_v1/output_img \
  --source-manifest artifacts/data_recovery/source_manifest_identity_v1.csv \
  --resolved-manifest artifacts/data_recovery/manifest_resolved.csv \
  --report artifacts/data_recovery/verification_report.json
```

The command checks the archive hash, restores only the canonical
`StrokeSegmentation/data/output_img` subtree, validates all 840 complete
samples, and proves each stacked mask equals the six independent masks. It
does not generate labels. The 200 model-derived reference-cache masks are
prohibited as GT.

Build and verify the QC layer:

```bash
python -m onestroke_model.scripts.build_dataset_qc
```

Formal configs use `artifacts/data_qc/manifest_qc_v1.csv` and
`artifacts/data_qc/character_disjoint_splits_qc_v1.csv`. Training,
threshold calibration, and evaluation validate their hashes and counts.

Generate or verify the frozen benchmark plan without training:

```bash
python -m onestroke_model.scripts.run_character_disjoint_benchmark
```

The default is always dry-run. The plan contains:

- one U-Net baseline run;
- three pre-registered SegFormer-B2 seeds;
- three DeepLabV3+ seed placeholders marked `BLOCKED_BY_TASK1`.

Thresholds must be calibrated on validation only. The test split is evaluated
once per completed run after the checkpoint and thresholds are fixed. The
original character assignment and the QC exclusion list must not change.

After Task 1 has supplied the authoritative DeepLabV3+ implementation and
replaced the three blocked placeholders, actual execution requires an explicit
flag:

```bash
python -m onestroke_model.scripts.run_character_disjoint_benchmark --execute
```

The launcher refuses execution if the data, split hash, split counts, or any
Task 1 run is not ready.
