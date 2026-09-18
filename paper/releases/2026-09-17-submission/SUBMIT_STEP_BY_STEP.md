# 一步步投稿操作指南（IJDAR 特刊）

截稿：**2026-09-20**。本指南按 SNAPP 投稿系统的标签页顺序写成，
从登录到点下 Submit 全流程。所有文件在本目录
`paper/releases/2026-09-17-submission/` 下。

---

## 第 0 步：开投前 5 分钟的准备

**手边要有这三样：**

1. 三位作者的 ORCID iD（16 位，末位可能是 `X`）；
2. 通讯作者能收到邮件的邮箱：`10244602411@stu.ecnu.edu.cn`；
3. 本目录下的三个投稿文件（见第 5 步）。

**要上传的文件（三个，别搞混）：**

| 文件 | 用途 |
| --- | --- |
| `OneStroke2026_manuscript_latex.zip` | **正文**（投稿系统的 Manuscript file 槽） |
| `OneStroke2026_ESM_1_submission.pdf` | 补充材料（Supplementary 槽） |
| `OneStroke2026_cover_letter.pdf` | 投稿信（Related files 槽） |

> ⚠️ **不要上传 `OneStroke2026_online_latex_submission.zip`**。那是给我们
> 三个和 Claude 在 Overleaf 上协作用的包（109 个文件，含内部说明和历史修订
> 文档），传上去会让出版方困惑。投稿只用 33 个文件那一个。

**可选：** 用浏览器打开 `OneStroke2026_manuscript_submission.pdf` 对着看，
那是终稿 PDF（20 页），上传后系统编译出来的应该和它一致。

---

## 第 1 步：进入投稿入口

1. 打开 <https://www.editorialmanager.com/> 一类入口不好使——IJDAR 用的是
   **SNAPP**，从期刊主页进去：
   <https://link.springer.com/journal/10032>
2. 点 **Submit your manuscript**，跳到 SNAPP。
3. 用通讯作者账号登录（没有就注册一个）。**建议直接用 ORCID 登录**，
   后面填作者信息时会自动带入。

---

## 第 2 步：选文章类型和特刊

新建投稿后，第一步是选 **Article type**：

- 文章类型选 **Original Paper**（或系统里对应的研究论文类型）；
- **关键**：如果有 **Special Issue** 下拉框，选
  **Computer Vision Systems for Document Analysis and Recognition**
  （就是我们要投的那个特刊）。**这一步选错，稿子会进普通通道，编辑可能
  直接退回让你重投。**

如果界面上找不到特刊选项，说明这一栏在后面某个标签页，先往后走，看到
Special Issue / Section 字样就选上。

---

## 第 3 步：Authors 标签页（填作者）

**逐个添加三位作者**，顺序按正文：Xiaofan Liu → Ronghao Zhang → Yuan Feng。

每位作者填写：

| 字段 | 怎么填 |
| --- | --- |
| Given name / Surname | Xiaofan / Liu，依此类推 |
| E-mail | 各自学校邮箱；通讯作者用 `10244602411@stu.ecnu.edu.cn` |
| **ORCID** | **每位都填**，16 位 iD，不用加网址前缀 |
| Affiliation | Software Engineering Institute, East China Normal University, Shanghai, China |
| Corresponding author | **只勾 Xiaofan Liu 一位** |

**三位是同等贡献（equal contribution）。** 这一条：

- 正文里已经用脚注 "These authors contributed equally to this work."
  标在三个人名字上；
- 如果系统有"Equal contribution"勾选框，三位都勾；没有就跳过，正文脚注
  已经说明。

> 作者顺序如有调整，务必告诉我对齐正文，不能让界面和 PDF 不一致。

---

## 第 4 步：Details 标签页（标题、摘要、关键词）

从 `DECLARATIONS.md` 里**逐字复制**，不要手打（手打容易出大小写和连字符
错误）：

**标题：**

```
Reference-Conditioned Structural Assessment of Low-Resource Chinese
Calligraphy with Overlapping Stroke Parsing and Human-Audited Spatial
Scoring
```

注意 `Reference-Conditioned`、`Low-Resource`、`Human-Audited` 三个连字符
不能丢。

**摘要：** 结构化摘要，228 词，含 Purpose / Methods / Results / Conclusion
四段。直接从 `OneStroke2026_manuscript_submission.pdf` 第 1 页复制，或从
`manuscript.tex` 的 `\abstract{}` 段取。

**关键词（6 个，逗号分隔）：**

```
Chinese calligraphy, document analysis, multi-label segmentation,
reference-based assessment, human validation, explainable feedback
```

如果系统限制关键词个数，6 个是合规的（期刊要求 4–6 个）。

---

## 第 5 步：Files 标签页（上传文件）

这是核心一步。按槽位对应：

| 系统槽位 | 上传 | 说明 |
| --- | --- | --- |
| **Manuscript file** | `OneStroke2026_manuscript_latex.zip` | 系统会**自己编译**成 PDF 送审 |
| **Figures and tables** | **留空** | 系统写明"接受后再提供高分辨率原图" |
| **Supplementary material** | `OneStroke2026_ESM_1_submission.pdf` | 4 页，表 S1–S4 + 注 S5–S6 |
| **Related files** | `OneStroke2026_cover_letter.pdf` | 给编辑的投稿信 |

**为什么正文传 zip 而不是 PDF：** 该页原文写明"LaTeX documents with figures
and tables compressed into a zip format. **We will compile these into a PDF
for peer review**"。所以传 zip 是它要求的做法。

**可选保险动作：** 把 `OneStroke2026_manuscript_submission.pdf` 也放到
**Related files** 里，这样编辑不编译也能立刻看到我们的排版效果。低风险，
可做可不做。

**上传后系统会显示它编译的结果**，务必点开看一眼：应该是 20 页、参考文献
是数字引用（如 [1]）、没有 `[?]` 问号。如果看到 `[?]`，说明它只编译了一遍，
一般再等等刷新即可；若一直如此，告诉我。

---

## 第 6 步：Declarations 标签页（声明）

这一页的每个字段，从 `DECLARATIONS.md` 对应小节**逐字复制**。字段清单：

- Competing Interests
- Funding
- Ethics Approval
- Informed Consent
- Consent for Publication
- Data Availability
- Code Availability
- Author Contributions

**为什么必须逐字一致：** 投稿系统写明，界面上填的这些信息**才会进最终
发表的文章**，正文里的声明不算。所以两处一旦不一致，出版后就是矛盾的，
这是最容易被审稿人/编辑抓的细节。`DECLARATIONS.md` 里的文本与正文逐字
一致，直接复制即可。

---

## 第 7 步：Review 标签页（提交前最后检查）

系统会生成一份 PDF 预览。**逐项核对这几点**：

- [ ] 标题、三位作者姓名与顺序正确
- [ ] 通讯作者标记在 Xiaofan Liu 上
- [ ] 摘要完整（四段都在，没被截断）
- [ ] 6 个关键词都在
- [ ] 正文 20 页，参考文献是数字引用
- [ ] 图 1、2、3 等图片都显示正常（不是空白框）
- [ ] 声明字段都填了
- [ ] 特刊选对了

**任何一项不对，先别点 Submit**，回上一步改，或告诉我。

---

## 第 8 步：提交

1. 点 **Submit**（有的系统要再点一次 **Approve submission** 确认）。
2. 页面会给出稿件编号（形如 `IJDAR-D-26-00XXX`），**记下来**。
3. 通讯作者邮箱会收到确认邮件，作者们可能都会收到。

**提交后系统通常锁定稿件，不能再改。** 所以第 7 步别省。

---

## 提交后会发生什么

1. **技术审查**（几天）：编辑部检查格式、声明、文件是否齐全。有问题会退
   回来让你补，这时可以改。
2. **分配编辑 → 送外审**（几周到几个月）。IJDAR 是同行评审期刊，正常周期
   不短。
3. **审稿意见回来**：可能是大修 / 小修 / 拒稿。修回时如果需要重编译、
   重画图或补实验，跟我说。

**期间保持通讯作者邮箱畅通**，编辑部的一切通知都发到那里。

---

## 常见坑（都踩过了，照着避）

1. **特刊没选** → 稿子进普通通道，可能被退回重投。第 2 步务必确认。
2. **传错 zip** → 别传 109 个文件那个协作包。
3. **声明字段留空或与正文不一致** → 界面里的才会进终版，必须照抄
   `DECLARATIONS.md`。
4. **ORCID 末位 `X` 当成数字打错** → 填完核对一遍。
5. **别在正文里加 `\orcid{}`** → 我们的 `sn-jnl.cls` 缺少 `Orcidlogo.eps`，
   会导致系统编译失败、投稿当场挂掉。ORCID 走界面填就够了。
6. **系统编译出 `[?]`** → 多数是只编译一遍，刷新看看；持续存在就告诉我。

---

## 只有你能决定的两件小事（不影响提交）

1. **投稿信日期**：现在写的是 17 September 2026。如果你在 19 或 20 日提交，
   我可以一分钟改成实际提交日并重编译（会刷新哈希）。不改也完全能用。
2. **数据归档 DOI**：如果你把 QC 契约、两个 split 和 769 样本存到
   Zenodo/Figshare（第三方参考图**不能**放进去），把 DOI 发我，我加进
   Data Availability。不存也不影响投稿。

---

## 一句话总结

登录 SNAPP → 选特刊 → 填三位作者（含 ORCID）→ 粘标题摘要关键词 →
上传 **zip + ESM PDF + 投稿信 PDF** 三个文件 → 粘声明 →
预览确认 20 页无误 → Submit。

卡在任何一步，把界面截图发我。
