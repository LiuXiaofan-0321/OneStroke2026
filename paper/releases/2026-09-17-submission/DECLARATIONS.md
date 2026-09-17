# Paste-ready text for the submission interface

The submission system states that author-contribution and competing-interest
information entered in the interface is what appears in the published
article. The blocks below match the manuscript verbatim, so the PDF and the
interface cannot drift apart. Copy each block into the matching field.

## Title

Reference-Conditioned Structural Assessment of Low-Resource Chinese
Calligraphy with Overlapping Stroke Parsing and Human-Audited Spatial
Scoring

## Authors and affiliation

Xiaofan Liu, Ronghao Zhang, Yuan Feng

Software Engineering Institute, East China Normal University, Shanghai,
China

Corresponding author: Xiaofan Liu, 10244602411@stu.ecnu.edu.cn

All three authors are marked as contributing equally. The manuscript carries
the footnote "These authors contributed equally to this work" on all three
names.

## Competing Interests

The authors declare no competing interests.

## Funding

This work was conducted within the East China Normal University Undergraduate
Innovation Training Incubation Project (Entrepreneurship Training category),
"OneStroke: A Vision-Model-Based Intelligent Feedback System for Chinese
Calligraphy". No external funding or grant number is recorded.

## Ethics Approval

Not applicable. The study analysed images of handwritten characters and
perceptual similarity ratings; it involved no clinical, medical, or
behavioural intervention on human subjects. The handwriting corpus was
commissioned by the project without recording writer identities, and the
structural-similarity ratings were provided by two of the authors and one
collaborating calligraphy specialist as part of the study design, stored
under evaluator codes, with no sensitive personal information collected.

## Informed Consent

Not applicable. No identifiable personal data of writers or raters are
reported; the three raters took part in the rating study voluntarily as
contributors to the project and were informed that the task assessed
character structure similarity, not their own ability.

## Consent for Publication

Not applicable. No identifying information about human participants is
reported.

## Data Availability

The frozen data contracts and result tables that support the reported values
are in the code repository named under Code Availability: the quality-control
audit and exclusion contract and both split assignments
(`artifacts/data_qc`, `artifacts/data_audit`,
`artifacts/paper_ijdar/character_disjoint`); the per-seed segmentation
results and checkpoint manifest (`artifacts/paper_ijdar/task1`); the ASDS
development features, character-grouped folds, frozen specification, and
report (`artifacts/paper_ijdar/spatial_score_development`); the 150-pair
direct-ink ASDS table (`artifacts/paper_ijdar/direct_ink_asds`); the
reference-library manifest with per-image source paths and SHA-256 digests
(`references/calli_tongji_beta_manifest.csv`); and the figure provenance
manifest. Online Resource 1, Note S6, lists the digests of every frozen
artifact. The external reference images are the Ouyang Xun regular-script and
Wang Xizhi running-script categories (100 images each) of the Calli-Tongji
open subset, publicly downloadable from ModelScope under CC BY-NC 4.0; they
are reproduced in Figures 1, 3 and 5 with attribution and are not
redistributed. The project-collected handwriting images and six-channel
masks, the controlled-perturbation, alignment-ablation, inactive-channel, and
cross-reference result files, and the blinded 150-pair rating files
(evaluator codes only) are available from the corresponding author on
reasonable request for non-commercial research use.

## Code Availability

Source code, frozen experiment contracts, analysis scripts, and
non-restricted reproducibility artifacts are maintained at
https://github.com/LiuXiaofan-0321/OneStroke2026; an identity-free archival
copy will be supplied if anonymous review is required.

## Author Contributions

X.L.: Conceptualization, methodology, software, formal analysis,
visualization, writing---original draft, project administration. R.Z.: Data
curation, methodology, software, validation, writing---review and editing.
Y.F.: Software, system integration, validation, writing---review and
editing. All authors contributed to the investigation, approved the submitted
manuscript, and accept responsibility for the work.

## Acknowledgements

The authors thank Chengcheng Wan for project supervision.

## Suggested reviewers

Optional. If the editors accept suggestions, supply two to four names with
institutional e-mail addresses, chosen from the related-work areas
(document image analysis, computational calligraphy, human-validated
assessment). Exclude anyone at East China Normal University.

## Two items that still need a decision before you submit

1. **Ethics wording.** The manuscript states "Not applicable" and cites no
   institutional reference. Confirm with your supervisor or the school office
   whether ECNU wants its own exemption wording here; if so, tell me and I
   will change both the manuscript and this file.
2. **Data archive identifier.** Springer encourages depositing supporting
   data in a public repository and citing its identifier. If you deposit the
   QC contract, the two split files, and the 769-sample corpus (the
   third-party reference images must stay out of that deposit), send me the
   DOI and I will add it to the Data Availability statement in the manuscript
   and here.
