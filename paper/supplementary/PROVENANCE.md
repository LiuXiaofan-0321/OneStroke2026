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
- `artifacts/paper_ijdar/course_scoring_scope/run_manifest.json`
- `artifacts/paper_ijdar/course_scoring_scope/course_overlap_summary.csv`
- `artifacts/paper_ijdar/task1/results_per_seed.csv`
- `artifacts/paper_ijdar/task1/results_summary.csv`
- `artifacts/paper_ijdar/task1/summary_manifest.json`
- `artifacts/paper_ijdar/task1/checkpoint_manifest.csv`
- `artifacts/paper_ijdar/task1/formal_audit_manifest.json`
- `artifacts/paper_ijdar/task1/formal_run_file_manifest.csv`
- `artifacts/paper_ijdar/task1/formal_runs/`
- `artifacts/paper_ijdar/spatial_score_development/development_report.json`
- `artifacts/paper_ijdar/spatial_score_development/development_features_and_predictions.csv`
- `artifacts/paper_ijdar/spatial_score_development/group_cv_folds.csv`
- `artifacts/paper_ijdar/spatial_score_development/frozen_spatial_score_v1.json`
- `artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_pairs.csv`
- `artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_report.json`
- `artifacts/paper_ijdar/direct_ink_asds/table_direct_ink_asds.tex`

Excluded:

- every directory containing `synthetic_smoke`;
- same-image/self-reference score examples near 100;
- empty human-rating templates;
- cross-character legacy-to-course score pairings;
- Task 1 smoke outputs and any incomplete formal run.
- the unused ASDS follow-up candidate images or pair lists as results of the
  present human study.

Human-validation safeguards:

- correlation and ICC use only the 150 canonical non-repeat presentations;
- the 15 hidden repeats are used only for intra-rater consistency;
- the three original return CSV files are retained byte-for-byte;
- the study supports structural-similarity claims, not aesthetic grading;
- the rater pool is described as blinded human raters rather than three
  independent calligraphy experts. The manuscript instead reports the
  author-confirmed domain qualifications and the partly non-independent
  composition of two author-raters and one non-author rater.

ASDS development safeguards:

- the original 150 ratings are explicitly treated as development data for
  ASDS;
- component choice and weight selection are not described as prospective;
- character-grouped out-of-fold predictions are labelled internal validation,
  not external confirmation;
- the generated 100-pair follow-up package is retained only as an optional
  future-study artifact and contributes no rating or result to the present
  manuscript.

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
- Task 1 per-seed result table SHA-256:
  `c6d27f365fab15b71914c6ae1ccaf723b02e236c28dc2b4a656ad7c50ea7934e`;
- Task 1 summary table SHA-256:
  `dcd2fa5248d8a1a0fa5143fbe72dd75ae3269551b8e58d071e1d0f638b6d1d6c`;
- Task 1 checkpoint manifest SHA-256:
  `f49c4fc8b364abe62eade730dc6f9b14e35d6baf809d5d7e5e6fb3d7462b391e`.
- frozen ASDS development specification SHA-256:
  `da79ace3dca2793f586ef721689cbb96e1a0e614155a8c94ff48f6cb7872fa4e`;
- ASDS development report SHA-256:
  `01fe8d62f368fbc45d5a4451a3d833ed1d75c7a4896c943e8c8590e790ec3083`;
- optional follow-up candidate manifest SHA-256:
  `6221f9ed9d28a1a93aeadd3b67c3fcb9761dfce45fd981b68ca7b1db0dcc026b`;
- optional follow-up candidate 100-pair CSV SHA-256:
  `51a9ee4c1b75a960e8fc2c35414158e9575c5056dd0e15141b1f662f13ceca30`.
- direct-ink ASDS paired-row table SHA-256:
  `ff39039f869fa5ff217792ff2b6a7fa2985e1770cbc7b247a36f7e90ae426bb3`;
- direct-ink ASDS report SHA-256:
  `44403497fd4980c834946b761b8352a1b05f49249f14c4a8f668affac36ac895`.
- direct-ink ASDS generated LaTeX table SHA-256:
  `c92277d9a494e62f9552e2b808c2baf777f7f94131cad100062ff89df63109cc`.

The 200 model-derived reference caches are not segmentation ground truth.

Manuscript layout note (2026-09-02):

- the main text is organized as Introduction, Related Work, Data Resources,
  Method, Experimental Setup, Results and Discussion by Research Question,
  General Discussion and Limitations, and Conclusion;
- Tables S1--S4 and Notes S5--S6 of Online Resource 1 (`ESM_1.tex`) carry
  the full perturbation statistics, the perturbation-level alignment
  ablation, the inactive-channel audit, the cross-reference test, the ASDS
  candidate search, and the integrity hashes listed above;
- the diagnostic metrics reported in the main text are required Recall@3,
  exact grid localization, and the exact-localization failure taxonomy; the
  additional diagnostic metrics recorded in
  `docs/PROJECT_WORK_SUMMARY_2026-08-13.md` (strict Top-1, overlap
  localization, specificity, centre-direction wording) are not quoted in the
  manuscript because their formal artifact directory is not tracked in this
  repository.
- of the paper-eligible result sources listed at the top of this file, the
  directories `artifacts/paper_ijdar/controlled_perturbation/`,
  `structure_score_audit/`, `cross_reference/`, `alignment_ablation/`,
  `feedback_diagnostic/`, `journal_statistics/`, and `expert_validation/`
  are kept outside the public Git history (licence-restricted reference
  masks and raw rating returns); the values quoted from them in the
  manuscript are cross-checked against `docs/PROJECT_WORK_SUMMARY_2026-08-13.md`
  and must be re-verified against the archived run manifests before
  submission.
