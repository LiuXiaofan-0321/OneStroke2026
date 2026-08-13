# OneStroke 840-Sample Ground-Truth Data Recovery Report

Date: 2026-08-12

## Executive conclusion

The 840 complete six-channel ground-truth samples have been found.

They are stored, without needing label reconstruction, in:

```text
C:\University Courses\大创项目\tmp\OneStroke-main.tar.gz
```

Archive SHA-256:

```text
b9924007099033cc8b62128dc2139ea9cb04a66a48e56c46518407677254450d
```

Canonical directory inside the archive:

```text
OneStroke-main/StrokeSegmentation/data/output_img/
```

The archive contains all 894 sample directories described by the current
manifest. Exactly 840 directories contain the complete training contract:

```text
0.jpg
0.npy
mask_1.npy
mask_2.npy
mask_3.npy
mask_4.npy
mask_5.npy
mask_key_point.npy
```

All 840 sample IDs marked complete in
`artifacts/data_audit/manifest.csv` occur as complete sample directories in the
archive. No complete manifest sample is missing and no extra sample ID is
introduced.

The data was subsequently restored into a versioned local directory and
exhaustively validated:

```text
data/legacy_gt_v1/output_img/
```

The resolved manifest and machine-readable verification report are:

```text
artifacts/data_recovery/manifest_resolved.csv
artifacts/data_recovery/verification_report.json
```

The repository also tracks a portable 894-row identity manifest without the
historical machine-specific paths:

```text
artifacts/data_recovery/source_manifest_identity_v1.csv
```

No training was run during this investigation or restoration.

## Post-recovery semantic QC

Recovery established that 840 samples are file-complete and that each stacked
mask equals the six independent masks. A later semantic QC pass established a
stricter training population:

```text
840 complete GT files
- 12 source-image/GT mismatches
- 59 exact image+mask duplicate non-canonical instances
= 769 QC-clean unique segmentation observations
```

The mismatch and duplicate exclusion sets do not overlap. The original
standard split contains no cross-split exact duplicate group, so the
preliminary B2 result is not explained by exact train-to-test duplicate
leakage. It nevertheless used mismatched and duplicate-weighted training data
and must be rerun for the paper.

Formal Task 1 and character-disjoint training must use:

```text
artifacts/data_qc/manifest_qc_v1.csv
artifacts/data_qc/dataset_qc_exclusions_v1.csv
```

Recovery answers file presence and internal completeness; semantic QC answers
whether observations are matched and independent.

## Non-negotiable integrity rules

1. The 200 SegFormer reference-cache files under
   `references/cache/segformer_b2_v1/` are model-derived reference masks. They
   are **not ground truth** and must never be used as replacements for the 840
   segmentation labels.
2. Missing labels must not be fabricated, predicted, or guessed merely to make
   training run.

## Evidence

### Current manifest

The current manifest declares:

- 894 total sample directories;
- 43 character directories;
- 840 complete samples;
- 54 samples with missing masks;
- historical root:
  a historical local temporary `StrokeSegmentation/data/output_img` path.

The historical temporary directory no longer exists locally.

### Recovered archive inventory

The recovered archive contains:

- 19,781 total archive entries;
- 894 sample directories under `StrokeSegmentation/data/output_img`;
- 43 character directories;
- 14,622 files immediately belonging to those sample directories;
- 840 stacked six-channel `0.npy` files;
- 840 copies of each independent mask required by the dataset contract;
- 894 input `0.jpg` images.

Archive-to-manifest comparison:

| Check | Result |
|---|---:|
| Manifest sample IDs found in archive | 894 / 894 |
| Complete manifest IDs found complete | 840 / 840 |
| Complete manifest IDs missing/incomplete | 0 |
| Archive sample IDs absent from manifest | 0 |

The initial forensic pass loaded representative arrays from the beginning,
middle, and end of the complete sample sequence with `allow_pickle=False`. The
subsequent restoration pass loaded and checked **all 840 complete samples**.
The observed format matches the manifest:

- independent masks: `[500, 500]`, Boolean;
- stacked masks: `[500, 500, 6]`, Boolean;
- values: binary `0/1`.

For every complete sample, the verifier asserted:

```text
0.npy == stack(
  mask_1.npy,
  mask_2.npy,
  mask_3.npy,
  mask_4.npy,
  mask_5.npy,
  mask_key_point.npy
)
```

All 840 comparisons passed exactly. Archive restoration also enforced the
pinned archive SHA-256 and rejected unsafe archive paths and special members.

The machine-readable forensic summary is stored at:

```text
artifacts/paper_ijdar/data_recovery_forensics.json
```

### GitHub and Git-history evidence

The old project is:

```text
https://github.com/Mmrliu-gooooood/OneStroke
```

At the time of investigation:

- remote branch: `main`;
- remote head: `7cffa3fbb29c5cbea8c9f7f3e485614b9ba77e49`;
- mirror pack size: approximately 542 MiB;
- the current Git tree itself contains the `output_img` dataset;
- Git history shows the dataset introduced in the 2025 development history;
- the repository has no additional public branch or tag containing a different
  dataset version.

The old Git tree contains 14,646 files below
`StrokeSegmentation/data/output_img`, including:

- 5,880 `.npy` files;
- 840 stacked `0.npy` files;
- 840 `mask_key_point.npy` files;
- 894 input `0.jpg` files.

The local `OneStroke-main.tar.gz` is sufficient for recovery even if the remote
repository later changes.

### Ground-truth provenance

The old repository preserves the label-generation chain:

```text
stroke_collector/
StrokeSegmentation/data/filter.py
StrokeSegmentation/data/mask.py
StrokeSegmentation/data/tools/tool.py
StrokeSegmentation/data/asset/stroke_vector_mapping.py
```

The collection tool exported:

- one complete-character image;
- one image for each independently written stroke.

The preprocessing code then:

1. normalized and binarized the complete-character image;
2. converted each exported stroke image into a binary region;
3. assigned the stroke region to one of five direction channels using the
   fixed, character-specific `STROKE_VECTOR_MAP`;
4. extracted green endpoint/keypoint evidence;
5. saved the five direction masks, keypoint mask, and stacked six-channel mask.

Therefore, the recovered 840 labels are derived from human stroke-isolated
source images plus an explicit deterministic mapping. They are not SegFormer
outputs.

## The 54 incomplete samples

The incomplete samples are character IDs `40`, `41`, and `42`, with 18 samples
per character. Their directories contain the complete image and individual
stroke images but no `.npy` masks.

They cannot currently be declared losslessly reconstructable because the
checked-in `STROKE_VECTOR_MAP` defines only character IDs `0–39`. The missing
40–42 direction mappings cannot be inferred safely from model output or visual
guesswork.

Decision:

- keep these 54 samples excluded from the 840-sample benchmark;
- do not generate their labels unless the original direction mapping or an
  authoritative human annotation record is recovered.

## Other locations investigated

### Local filesystem

Checked:

- historical Codex temporary path;
- current project tree;
- Downloads;
- July WeChat file-transfer directory;
- project-local archives;
- current repository history, branches, tags, and stash;
- documentation, logs, and source files for absolute paths and sample naming.

Important local artifacts found:

- `C:\University Courses\大创项目\tmp\OneStroke-main.tar.gz` — complete recovery source;
- a local `OneStroke2026_github_upload_only.zip` — current-project
  packaging, not the missing GT source;
- a local `segformer_v1_metrics_20260725.tar.gz` — metrics,
  not GT;
- `zhang_ronghao_task_1_3_deliverables_20260712.tar.gz` — task deliverables,
  not the canonical GT source.

### AutoDL

Earlier project checks established that the active AutoDL project directory no
longer contained the original `output_img`; it contained the trained model,
reference cache, and experiment artifacts. A new non-interactive SSH attempt on
2026-08-12 could not authenticate because no SSH key is configured, and the
password was deliberately not embedded in a command or script.

Because the canonical 840 samples were recovered and matched locally, further
password-based server searching is not required for data recovery.

## Human actions still recommended

1. Copy the archive to at least one second durable location, such as an
   institutional drive or private release storage.
2. Rotate the AutoDL password previously exposed in chat and configure SSH-key
   authentication.
3. Ask the previous data collector whether the missing character IDs `40–42`
   have an original direction-mapping sheet. Only that authoritative mapping
   could make the 54 samples losslessly reconstructable.
4. Preserve the restored dataset and resolved manifest together. If moved to a
   new machine, rerun the supplied restoration command there so paths are
   resolved and all arrays are revalidated before training.

## Recovery status

| Item | Status |
|---|---|
| 840 original complete GT samples | FOUND |
| Versioned local restoration | COMPLETE |
| Exact manifest correspondence | VERIFIED |
| Six-channel schema | VERIFIED |
| All 840 stacked/independent mask comparisons | VERIFIED |
| Non-model-derived provenance | VERIFIED |
| 200 reference cache usable as GT | PROHIBITED |
| 54 incomplete samples | EXCLUDED |
| 54-sample lossless reconstruction | BLOCKED_BY_MISSING_MAPPING |
| Training executed during recovery | NO |

## Reproduction command

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.restore_legacy_gt `
  --archive "C:\University Courses\大创项目\tmp\OneStroke-main.tar.gz" `
  --destination "data\legacy_gt_v1\output_img" `
  --source-manifest "artifacts\data_audit\manifest.csv" `
  --resolved-manifest "artifacts\data_recovery\manifest_resolved.csv" `
  --report "artifacts\data_recovery\verification_report.json"
```

This command extracts original files only. It does not run a model, generate
labels, or repair missing masks.
