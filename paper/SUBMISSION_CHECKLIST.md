# IJDAR Special Issue submission checklist

Status date: 2026-08-14

## P0: required before submission

- [ ] Submit by **September 20, 2026**, selecting the Special Issue
  *Computer Vision Systems for Document Analysis and Recognition*.
- [ ] Internally review all 100 confirmatory candidate pairs without viewing
  any model or human score.
- [ ] Replace any rejected pair only by the frozen reserve order.
- [ ] Freeze and hash `frozen_confirmatory_pairs_v1.csv`.
- [ ] Freeze ASDS code, bins, weights, alignment, rating instructions, primary
  endpoint, exclusion policy, and analysis script before the first new rating.
- [ ] Collect confirmatory ratings on the frozen set.
- [ ] Run the frozen confirmatory analysis once.
- [ ] Replace `[CONFIRMATORY ASDS RHO, 95% CI, AND PAIRED DIFFERENCES]` only
  with the generated result.
- [ ] If confirmation fails, report the failure and retain the production
  score; do not tune ASDS on the confirmatory set.
- [ ] Fill author names, affiliation, corresponding email, acknowledgements,
  funding, CRediT roles, ethics approval/exemption, consent, code availability,
  and data availability.
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
- [x] Post-rating ASDS development clearly separated from confirmation.
- [ ] Confirmatory analysis executed from frozen artifacts.

## Manuscript checks

- [x] Springer Nature `sn-jnl`, `iicol`, `sn-basic`.
- [x] Structured abstract within 150--250 words.
- [x] Six keywords (journal requirement: 4--6).
- [x] RQ-based introduction and contribution list.
- [x] Real, verifiable bibliography; no provisional UniCalli citation.
- [x] Limitations include unavailable writer ID, within-corpus confirmation,
  small rater pool, and no universal aesthetic claim.
- [x] Draft compiles without overfull boxes or unresolved citations.
- [ ] Remove every red placeholder.
- [ ] Re-run final PDF visual inspection.
- [ ] Verify final page count against the Special Issue instruction.
- [ ] Keep the final manuscript at or below 20 pages, including references,
  figures, and tables.
- [ ] Add the 50--100-word author biographies and separate author photographs
  requested by the journal instructions.
- [ ] Select the correct Special Issue during submission.
- [ ] Archive code, configuration, hashes, tables, and analysis outputs.

## Language that is allowed

- “reference-conditioned structural agreement”
- “human-validated structural similarity”
- “development-stage ASDS result”
- “character-disjoint generalization”

## Language that is not supported

- “expert aesthetic score”
- “universal calligraphy grading”
- “writer-disjoint generalization”
- “stroke-order recognition”
- “ASDS independently achieves rho=0.556”
- “three calligraphy experts”
