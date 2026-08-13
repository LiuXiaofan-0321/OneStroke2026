# Dataset QC Report V1

Generated: `2026-08-13T12:21:17.392103+00:00`

## Frozen decision

- Recovered complete GT files: **840**.
- Source-image/GT mismatches excluded: **12**.
- Exact image+mask duplicate non-canonical instances excluded: **59**.
- QC-clean unique segmentation observations: **769**.

The 200 SegFormer reference-cache masks are model outputs and are prohibited as
segmentation ground truth. No label is generated, repaired, or fabricated here.

## Standard split

- Before QC: `{'train': 600, 'val': 120, 'test': 120}`
- After QC: `{'train': 530, 'val': 119, 'test': 120}`
- Mismatches by split: `{'train': 12}`
- Duplicate non-canonical instances by split: `{'train': 58, 'val': 1}`
- Cross-split exact duplicate groups: **0**

## Character-disjoint split

- Before QC: `{'train': 588, 'val': 126, 'test': 126}`
- After QC: `{'train': 539, 'val': 114, 'test': 116}`
- Mismatches by split: `{'train': 7, 'val': 3, 'test': 2}`
- Duplicate non-canonical instances by split: `{'train': 42, 'val': 9, 'test': 8}`
- Cross-split exact duplicate groups: **0**

The original character assignment and its frozen SHA-256 remain unchanged.
QC is a predeclared exclusion layer applied after that assignment.

## Training rule

Task 1 and the character-disjoint benchmark must use the tracked QC-clean split
files and the exact exclusion-list SHA-256 recorded in the JSON report.
The preliminary July B2 release remains engineering evidence only.
