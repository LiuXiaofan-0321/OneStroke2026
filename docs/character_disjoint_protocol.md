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
- stable exclusion-contract SHA-256:
  `bd2b0641d0e6f53f6f18f6604232c02ff99e9d989eb39125f6a9af41e8573a1a`.

The full diagnostic exclusion CSV retains decoded-pixel hashes and IoU values.
It is not the cross-platform training contract because JPEG decoders can
produce a few different intensity values across `libjpeg` versions. The
71-row stable contract contains only the frozen exclusion decisions, reasons,
and canonical duplicate representatives.

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
python -m onestroke_model.scripts.run_task1_benchmark
```

The default is always dry-run. The complete plan contains:

- three models: U-Net, DeepLabV3+, and SegFormer-B2;
- two splits: standard QC-clean and character-disjoint QC-clean;
- three pre-registered seeds per model and split;
- 18 formal runs in total.

Thresholds must be calibrated on validation only. The test split is evaluated
once per completed run after the checkpoint and thresholds are fixed. The
original character assignment and the QC exclusion list must not change.

The real ResNet-50/ASPP/low-level-decoder DeepLabV3+ implementation and all
18 configs are present. Actual execution still requires an explicit flag:

```bash
python -m onestroke_model.scripts.run_task1_benchmark --execute
```

The launcher validates all data contracts before training and skips only runs
that already contain a checkpoint, validation-calibrated thresholds, and final
test metrics. Formal training results remain pending until the 18-run matrix
has actually completed.
