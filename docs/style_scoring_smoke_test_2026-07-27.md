# Reference-Based Style Scoring Smoke Test

Date: 2026-07-27

## Purpose

This is an engineering smoke test for the reference-conditioned structural scoring
pipeline. It verifies the complete path from image input through SegFormer-B2
six-channel segmentation, same-character reference retrieval, restricted global
alignment, and structured evidence output.

It is not a benchmark of calligraphy quality or a calibrated aesthetic score.

## Fixed Components

- Segmentation model: `segformer-b2-v1`
- Checkpoint SHA-256:
  `64df27aafc0eeecc07c0ac52c6ff00eef6b290ae7baf964cd5cf786262f395ce`
- Reference set: Calli-Tongji Beta, 200 approved single-character references
- Cache: 200 six-channel B2 mask records, 512x512 letterbox canvas
- Alignment: translation, isotropic scaling from 0.80 to 1.20, and rotation up
  to +/-3 degrees; nonuniform scaling and deformable warping are prohibited

## Controlled Comparison

Input image: the Calli-Tongji Beta image for the character `亮` labelled as
Ouyang Xun regular script. The input, target character, B2 checkpoint, thresholds,
and alignment policy were held constant. Only the selected reference style changed.

| Reference style | Prototype structure score | Direction Macro Dice | Ink IoU | Keypoint tolerant F1 (3 px) |
| --- | ---: | ---: | ---: | ---: |
| Ouyang Xun regular script (same-style control) | 99.9663 | 0.9995 | 0.9997 | 1.0000 |
| Wang Xizhi running script (cross-style control) | 9.9082 | 0.0754 | 0.1818 | 0.0609 |

The same-style control selected the identity transform: scale 1.00, rotation 0.0
degrees, and translation (0, 0). The cross-style control remained low after the
best allowed transform: scale 1.05, rotation 1.0 degrees, and translation (-38, 10).

## Interpretation

The approximately 90-point separation demonstrates that the current pipeline is
operational and responds to structured differences between the two selected
same-character references. The result does not establish a general-purpose
calligraphy grade, author classifier, or learned font-generation system. The score
must be presented as `prototype_structure_score`: transparent B2 mask-structure
agreement under an explicitly selected reference style.

## Next Validation

1. Repeat the positive/cross-style controls for the remaining shared characters:
   `功`, `勑`, `弃`, `嵗`, `尉`, and `息`.
2. Run the same protocol on real user handwriting for each supported character.
3. Collect blinded reviews from calligraphy-domain evaluators and calibrate score
   bands and feedback wording against those reviews.
