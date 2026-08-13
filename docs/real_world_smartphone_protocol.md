# Smartphone and Unseen-Writer Evaluation Protocol

## Status

`PENDING_DATA_COLLECTION`

No simulated smartphone results may be reported. Formal evaluation begins only
after consent, institutional ethics requirements, provenance, and local files
have been validated.

## Recommended scope

- Approximately 100-200 real smartphone photographs.
- Anonymized writer IDs.
- Multiple characters, lighting conditions, backgrounds, and device categories.
- Writer-disjoint reporting: no writer may appear in both adaptation/training
  data and the final real-world test set.

## Required metadata

The generated manifest template records:

- anonymized writer ID;
- character ID;
- image path and provenance;
- coarse device type;
- lighting and background category;
- annotation status;
- consent status;
- ethics approval/exemption/not-required confirmation.

Do not collect unnecessary names, phone numbers, student numbers, account IDs,
or other sensitive personal information.

## Ground-truth distinction

- Samples with reviewed six-channel masks may be used for Direction Macro Dice,
  Macro IoU, Boundary F1, strict Keypoint F1, and tolerant Keypoint F1.
- Samples without six-channel ground truth may only support clearly labelled
  qualitative or end-to-end structural-scoring analysis.
- Never mix these two groups into a single segmentation metric.

## Prepare templates

```bash
python -m onestroke_model.scripts.prepare_real_world_smartphone_templates \
  --output-dir artifacts/paper_ijdar/real_world/templates
```

## Validate before evaluation

```bash
python -m onestroke_model.scripts.validate_real_world_smartphone_manifest \
  --manifest artifacts/paper_ijdar/real_world/smartphone_manifest.csv \
  --output artifacts/paper_ijdar/real_world/manifest_validation.json \
  --require-local-images
```

Any failed consent or ethics field blocks formal processing.
