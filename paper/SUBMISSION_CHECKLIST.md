# IJDAR Special Issue submission checklist

Status date: 2026-08-14

## P0: required before submission

- [ ] Submit by **September 20, 2026**, selecting the Special Issue
  *Computer Vision Systems for Document Analysis and Recognition*.
- [x] Preserve the original 150-pair rating files, blinded assets, hashes, and
  hidden-repeat records.
- [x] Report the full ASDS candidate search, component ablations,
  character-cluster uncertainty, and character-grouped out-of-fold estimate.
- [x] Label `rho=0.556` as retrospective development and `rho=0.540` as
  internal validation; do not call either prospective or external
  confirmation.
- [ ] Verify the raters' background metadata and disclose any author-rater
  relationship accurately.
- [x] Fill author names, affiliation, corresponding email, acknowledgements,
  funding, CRediT roles, code availability, and data availability.
- [ ] Obtain institution-confirmed ethics approval/exemption wording and
  confirm the consent-for-publication statement.
- [ ] Confirm whether project-owned qualitative glyphs may be included in the
  submitted source package and public repository.

## Statistical checks

- [x] Three seeds retained for all 18 formal segmentation runs.
- [x] Validation-only threshold calibration.
- [x] Exact duplicate leakage audit.
- [x] Character-disjoint split frozen before formal evaluation.
- [x] Reference-cluster bootstrap for perturbation statistics.
- [x] Paired alignment comparison.
- [x] Character-cluster bootstrap for human correlation.
- [x] ICC(2,1), ICC(2,k), and hidden-repeat reliability.
- [x] Post-rating ASDS development clearly separated from grouped internal
  validation and future external replication.
- [x] Direct-ink ASDS compared with parsed-union ASDS under identical frozen
  alignment and score settings.

## Manuscript checks

- [x] Springer Nature `sn-jnl`, `iicol`, `sn-basic`, `Numbered`.
- [x] Structured abstract within 150--250 words.
- [x] Six keywords (journal requirement: 4--6).
- [x] RQ-based introduction and contribution list.
- [x] Numeric bracketed citations and numbered reference list.
- [x] Six-channel definition figure with endpoint-only keypoint semantics.
- [ ] Generate and insert the frozen Input/GT/U-Net/DeepLabV3+/SegFormer-B2
  qualitative figure after recovering the seed-20260811 formal checkpoints.
- [x] Real, verifiable bibliography; no provisional UniCalli citation.
- [x] Limitations include unavailable writer ID, within-corpus internal
  validation,
  small rater pool, and no universal aesthetic claim.
- [x] Draft compiles without overfull boxes or unresolved citations.
- [x] Remove every red placeholder.
- [ ] Re-run final PDF visual inspection.
- [ ] Verify final page count against the Special Issue instruction.
- [ ] Keep the final manuscript at or below 20 pages, including references,
  figures, and tables.
- [x] Draft 50--100-word author biographies in `AUTHOR_BIOGRAPHIES.md`.
- [ ] Have each author approve the biography wording and provide a separate
  author photograph.
- [ ] Select the correct Special Issue during submission.
- [ ] Archive code, configuration, hashes, tables, and analysis outputs.

## Language that is allowed

- “reference-conditioned structural agreement”
- “human-audited structural similarity”
- “development-stage ASDS result”
- “retrospective ASDS development”
- “character-grouped internal validation”
- “character-disjoint generalization”

## Language that is not supported

- “expert aesthetic score”
- “universal calligraphy grading”
- “writer-disjoint generalization”
- “stroke-order recognition”
- “ASDS independently achieves rho=0.556”
- “three calligraphy experts”
- “prospectively confirmed ASDS”
