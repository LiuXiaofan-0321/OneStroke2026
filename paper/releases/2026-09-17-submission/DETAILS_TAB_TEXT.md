# Details 标签页：可直接复制的文本（2026-09-19）

界面原文要求：*"It must match the title as it appears in your manuscript
file."* 所以下面三段都是从终稿 PDF 里逐字提取的，**不要手打**。

---

## 1. Title（原样粘贴，一行）

```
Reference-Conditioned Structural Assessment of Low-Resource Chinese Calligraphy with Overlapping Stroke Parsing and Human-Audited Spatial Scoring
```

标题里三处连字符必须保留：`Reference-Conditioned`、`Low-Resource`、
`Human-Audited`。标题中无数学公式，可放心直接粘。

---

## 2. Abstract（原样粘贴，约 228--229 词）

> 词数按切分口径略有出入（连字符复合词、数学量 `0.9630 ± 0.0006` 算一个还是
> 三个词），228 与 229 都成立，投稿信里采用的是 228。无论哪种口径都远在期刊
> 150--250 词的区间内，不影响合规。

四个小标题 `Purpose:` `Methods:` `Results:` `Conclusion:` 用界面的 **B**
按钮加粗（与稿件一致）。粘贴后请检查两处符号：

- `±`（正负号）在 `(0.9630 ± 0.0006)` 和 `(0.8866 ± 0.0008)` 里各一次；
- `Δρ` 在 `(Δρ = 0.0004)` 里出现一次，是希腊字母大写 delta + rho。

若某个符号粘进去变成乱码或问号，用界面的上下标/插入符号功能补，不要改成
`+/-` 或 `Drho` 之类的替代写法。

```
Purpose: Calligraphy, the brush-written Chinese art whose seal, clerical, regular, running, and cursive styles differ in stroke technique, is a foundation of traditional culture, yet two legible instances of the same character can still differ in the local structure that instruction attends to. We formulate reference-conditioned structural assessment as an auditable document-analysis task under limited labelled data.

Methods: A six-channel parser predicts five overlapping direction masks and an endpoint mask. U-Net, DeepLabV3+, and SegFormer-B2 are compared over three seeds on standard and character-disjoint splits of 769 quality-controlled samples. We evaluate constrained registration and diagnostic evidence on cached masks from 200 references under controlled perturbations. Three scores are assessed on 150 natural pairs rated blindly by three domain-qualified raters, two of them authors.

Results: DeepLabV3+ leads standard-split direction Macro Dice (0.9630 ± 0.0006); SegFormer-B2 leads character-disjoint direction parsing (0.8866 ± 0.0008); U-Net leads strict endpoint F1. Registration reduces nuisance penalties by 30.118 points relative to no alignment on clipping-safe cases while raising structural penalties by 11.189. The production, coverage-aware, and retrospectively developed aligned spatial-distribution similarity (ASDS) scores reach Spearman correlations of 0.297, 0.429, and 0.556. Character-grouped out-of-fold ASDS retains 0.540; direct-ink ASDS shows nearly identical association (Δρ = 0.0004). Localized evidence reaches Recall@3 of 0.701 but exact-cell localization of 0.109.

Conclusion: The framework separates scalar structural agreement from direction-specific diagnostic evidence, with explicit limits on generalization, human validity, and localization.
```

> 摘要正文里**没有关键词**，关键词在另一个字段，见下。

---

## 3. Keywords（如果本页或后面有该字段）

```
Chinese calligraphy, document analysis, multi-label segmentation, reference-based assessment, human validation, explainable feedback
```

共 6 个，逗号分隔，符合期刊 4--6 个的要求。

---

## 4. Cover letter 栏（本页下方，有 Upload cover letter 按钮）

**这一步的发现：投稿信在这里上传，不是在 Files 标签页的 Related files。**
既然系统给了专用入口，就用它。

点 **Upload cover letter**，选：

```
C:\Users\18963\Downloads\OneStroke2026_submission_20260917\OneStroke2026_cover_letter.pdf
```

（2 页，80 KB，字体全嵌入。）Files 标签页的 **Related files 留空**即可
——那一栏是给"同作者在审论文、实验室验证报告、私人通信"用的，我们没有
这类材料。
