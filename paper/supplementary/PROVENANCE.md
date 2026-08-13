# Manuscript provenance and integrity gate

Paper-eligible result sources:

- `artifacts/paper_ijdar/controlled_perturbation/run_manifest.json`
- `artifacts/paper_ijdar/structure_score_audit/run_manifest.json`
- `artifacts/paper_ijdar/cross_reference/run_manifest.json`
- `artifacts/paper_ijdar/alignment_ablation/run_manifest.json`
- `artifacts/paper_ijdar/feedback_diagnostic/run_manifest.json`
- `artifacts/paper_ijdar/journal_statistics/journal_statistics_manifest.json`
- `artifacts/data_recovery/verification_report.json`
- `artifacts/data_recovery/manifest_resolved.csv`
- `artifacts/data_qc/dataset_qc_report_v1.json`
- `artifacts/data_qc/dataset_qc_exclusions_v1.csv`
- `artifacts/data_qc/dataset_qc_exclusion_contract_v1.csv`
- `artifacts/data_qc/manifest_qc_v1.csv`
- `artifacts/data_qc/standard_splits_qc_v1.csv`
- `artifacts/data_qc/character_disjoint_splits_qc_v1.csv`
- `artifacts/paper_ijdar/expert_validation/frozen_study_v1/freeze_manifest.json`
- `artifacts/paper_ijdar/expert_validation/human_ratings_v1/raw_returns/`
- `artifacts/paper_ijdar/expert_validation/human_ratings_v1/merged_ratings.csv`
- `artifacts/paper_ijdar/expert_validation/human_ratings_v1/paper_statistics/human_validation_report.json`

Excluded:

- every directory containing `synthetic_smoke`;
- same-image/self-reference score examples near 100;
- empty human-rating templates;
- missing smartphone manifests;
- Task 1 or character-disjoint placeholders without completed run manifests.

Human-validation safeguards:

- correlation and ICC use only the 150 canonical non-repeat presentations;
- the 15 hidden repeats are used only for intra-rater consistency;
- the three original return CSV files are retained byte-for-byte;
- the study supports structural-similarity claims, not aesthetic grading;
- the rater pool is described as blinded human raters rather than three
  calligraphy experts.

Frozen facts:

- reference cache index SHA-256:
  `6d14374fda04de3957b29a874d16cbf986ccbc1f1d8be1bcfab8285f0fd9f00d`;
- SegFormer-B2 checkpoint SHA-256:
  `64df27aafc0eeecc07c0ac52c6ff00eef6b290ae7baf964cd5cf786262f395ce`;
- character-disjoint split SHA-256:
  `eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e`;
- QC-clean character-disjoint split SHA-256:
  `e9303314d1b70d3f92efcdc5c0807f833148cbe64c2702379f0ac951ed2a1e2b`;
- stable dataset QC exclusion-contract SHA-256:
  `bd2b0641d0e6f53f6f18f6604232c02ff99e9d989eb39125f6a9af41e8573a1a`;
- recovered legacy archive SHA-256:
  `b9924007099033cc8b62128dc2139ea9cb04a66a48e56c46518407677254450d`.
- frozen human-validation pair file SHA-256:
  `810d35e4e4bd0208de9608054daabaecc3613859f3a34c5a16e5141e266d8e66`;
- E01 return SHA-256:
  `347c423920c145c7a0b80753ad49db986d217bf7e8d1bad6e53642a8f3d7460e`;
- E02 return SHA-256:
  `a4376e5a4c2af0e71b97953d579b77e6ff51acf0cf011ebca9427385d4ee74c7`;
- E03 return SHA-256:
  `a2e1960c8257728d19790d6af80bf872406623a72203c056b63a81a9b8d189a0`.

The 200 model-derived reference caches are not segmentation ground truth.
