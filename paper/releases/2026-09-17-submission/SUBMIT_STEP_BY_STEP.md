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
| `OneStroke2026_cover_letter.pdf` | 投稿信（**Details 页的 Cover letter 栏**） |

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

- **文章类型选 `Research`（研究论文）。不要选 `Survey`。** 我们的稿子是
  一手研究：提出了新的六通道重叠表示、做了三种模型 × 三个随机种子的对比
  实验、做了受控扰动与配准消融、招募了三位有书法背景的评分者完成 150 对
  盲评、并据此提出并验证了 ASDS。`Survey` 指的是**综述**——不产生新实验，
  而是系统梳理他人成果。二者期望完全不同：选成 Survey，编辑会按"是否全面
  覆盖了领域文献"来审，而我们的参考文献是围绕方法选的重点文献，不是系统性
  综述，会被认为不符。**选 `Research`。**
- **关键**：如果有 **Special Issue** 下拉框，选
  **Computer Vision Systems for Document Analysis and Recognition**
  （就是我们要投的那个特刊）。**这一步选错，稿子会进普通通道，编辑可能
  直接退回让你重投。**

> 若下拉框的措辞不是 `Research`/`Survey`，而是 `Original Paper`、
> `Research Article`、`Regular Paper` 一类，同样是**选研究论文那一项**，
> 排除 `Review`、`Survey`、`Comment`、`Editorial`。

如果界面上找不到特刊选项，说明这一栏在后面某个标签页，先往后走，看到
Special Issue / Section 字样就选上。

---

## 第 3 步：Authors 标签页（先填机构，再填作者）

这一页分成上下两段：**Affiliated institutions**（机构）和
**Authors' information**（作者）。**先填机构并保存，再去作者的
Primary affiliation 下拉框里选它**——机构没保存前，下拉框是空的。

### 3.1 Affiliated institutions（机构）

四个字段这样填：

| 字段 | 填什么 |
| --- | --- |
| **Institution name** | `East China Normal University` |
| **Institution country or territory** | 下拉框选 `China` |
| **Institution city** | `Shanghai` |
| **Institution details**（可选） | `Software Engineering Institute` |

**要点：机构名填大学，学院填在 details 里。** 系统的示例就是
"Institution details (E.g. Department of Physics)"，说明这一栏是放院系的。
把 `Software Engineering Institute` 放这里，最终拼出来才是
"Software Engineering Institute, East China Normal University, Shanghai,
China"，与正文第 1 页的署名一致。

> 若 Institution name 输入时弹出联想列表（带 ROR ID 的那种），**选列表里
> 的官方条目**，别手打后直接保存——手打容易和官方名称有细微出入。

填完点 **Save institution information** 保存。系统写明每位作者最多挂两个
机构，我们每位只挂这一个。

### 3.2 Authors' information（作者）

系统要求 "Add all author names in the order they should appear in the
published manuscript"，所以顺序必须是：

**Author 1 Xiaofan Liu → Author 2 Ronghao Zhang → Author 3 Yuan Feng**

| 作者 | Given names | Family name | Email |
| --- | --- | --- | --- |
| Author 1 | `Xiaofan` | `Liu` | `10244602411@stu.ecnu.edu.cn` |
| Author 2 | `Ronghao` | `Zhang` | **待你提供**（见下方提醒） |
| Author 3 | `Yuan` | `Feng` | **待你提供**（见下方提醒） |

**🚨 最危险的坑：Given names 和 Family name 不能填反。**

中国人姓名在这里最容易出事。**Family name（姓）是 Liu / Zhang / Feng，
Given names（名）是 Xiaofan / Ronghao / Yuan。** 填反了，最终发表出来就是
"Liu Xiaofan"、"Zhang Ronghao"、"Feng Yuan"——国外读者看不出，但国内一看
就知道错了，而且**发表后很难改**。填完逐个核对一遍。

**🚨 另两位作者的邮箱现在缺。** 我查了整个仓库，只有刘小凡的
`10244602411@stu.ecnu.edu.cn` 有记录，张荣昊和冯缘的邮箱没有。这一栏标注
的是 "Institutional email if you have one"——优先用学校邮箱。**请你现在去
问他们两位要邮箱**，这一页填不下去就卡住了。

**每位作者的 Primary affiliation** 在下拉框里选刚保存的那一个
（East China Normal University）。Other affiliation 留空。

### 3.3 三个必须找一找的字段

这张截图里还看不到下面三项，它们**可能每位作者展开后才出现，也可能在
保存作者后出现在别处**，务必找到：

1. **ORCID**：**三位都要填**，16 位 iD，末位可能是字母 `X`，不用加
   `https://orcid.org/` 前缀。最终发表文章上的 ORCID 就取自这里，**不取自
   我们的 LaTeX 源码**。先把三个 iD 抄进 `DECLARATIONS.md` 的自查栏，免得
   现场翻手机。
2. **Corresponding author（通讯作者）**：**只标 Xiaofan Liu 一位。**
   正文第 1 页的星号 `*` 就在他名字上（`Xiaofan Liu1*†`），必须一致。
3. **Equal contribution（同等贡献）**：正文有脚注 "These authors
   contributed equally to this work." 标在三人名字上。系统若有该勾选框，
   **三位都勾**；完全没有就跳过，正文脚注已经说明。

> 作者顺序、姓名拼写、通讯作者标记这三项，一旦和正文 PDF 不一致就是硬伤。
> 填完回 `OneStroke2026_manuscript_submission.pdf` 第 1 页对一遍。

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

标题粘成**一行**（上面为排版折行，不要粘进换行）。注意
`Reference-Conditioned`、`Low-Resource`、`Human-Audited` 三个连字符不能丢。
完整可复制版见 `DETAILS_TAB_TEXT.md` 第 1 节。

**摘要：** 结构化摘要，约 228 词，含 Purpose / Methods / Results / Conclusion
四段。**完整纯文本已备好，见 `DETAILS_TAB_TEXT.md` 第 2 节，直接整块复制**。
四处需要核对：`±` 出现两次（在 `(0.9630 ± 0.0006)` 与
`(0.8866 ± 0.0008)`），`Δρ` 出现一次（在 `(Δρ = 0.0004)`）。若某个符号粘成
乱码，用界面的插入符号功能补，**不要**改成 `+/-` 或 `Drho` 之类写法。

**Cover letter（同一页下方）：** 点 **Upload cover letter**，上传

```
C:\Users\18963\Downloads\OneStroke2026_submission_20260917\OneStroke2026_cover_letter.pdf
```

系统在本页给了投稿信专用入口，所以它**不**走 Files 页的 Related files。

**关键词（6 个，逗号分隔）：**

```
Chinese calligraphy, document analysis, multi-label segmentation,
reference-based assessment, human validation, explainable feedback
```

如果系统限制关键词个数，6 个是合规的（期刊要求 4–6 个）。

---

## 第 5 步：Files 标签页（上传正文和补充材料）

这是核心一步。按槽位对应：

| 系统槽位 | 上传 | 说明 |
| --- | --- | --- |
| **Manuscript file** | `OneStroke2026_manuscript_latex.zip` | 系统会**自己编译**成 PDF 送审 |
| **Figures and tables** | **留空** | 系统写明"接受后再提供高分辨率原图" |
| **Supplementary material** | `OneStroke2026_ESM_1_submission.pdf` | 4 页，表 S1–S4 + 注 S5–S6 |
| **Related files** | **留空** | 这一栏是给"同作者在审论文、实验室验证报告、私人通信"用的，我们没有这类材料。**投稿信不在这里**——Details 页有专用上传入口，见第 4 步。 |

**为什么正文传 zip 而不是 PDF：** 该页原文写明"LaTeX documents with figures
and tables compressed into a zip format. **We will compile these into a PDF
for peer review**"。所以传 zip 是它要求的做法。

**可选保险动作：** 若希望编辑不编译也能立刻看到排版效果，可把
`OneStroke2026_manuscript_submission.pdf` 放进 **Related files**。低风险，
可做可不做；不做更干净。

**上传后系统会显示它编译的结果**，务必点开看一眼：应该是 20 页、参考文献
是数字引用（如 [1]）、没有 `[?]` 问号。如果看到 `[?]`，说明它只编译了一遍，
一般再等等刷新即可；若一直如此，告诉我。

---

## 第 6 步：Declarations 标签页（声明）

这一页有**八个独立的问答块**，从纯勾选到需要粘贴长文本的都有。逐块对照：

| # | 区块 | 怎么填 |
| --- | --- | --- |
| 1 | **Publishing policy** | 勾选那个复选框 |
| 2 | **Competing interests** | 选第一项 **No** |
| 3 | **Dual publication** | 选第一项 **No** |
| 4 | **Authorship** | 勾选那个复选框 |
| 5 | **Third party material** | 选第一项 **No**（见下方专段） |
| 6 | **Data availability** | 选 **Yes. I used or generated research data**，然后粘贴声明 |
| 7 | **Acknowledgements**（可选） | 粘贴致谢那句 |
| 8 | **Research funding** | 选 **No**（已定，与正文一致） |

**贯穿全页的一条铁律：界面上填的才会进最终发表的文章。** 界面上多个区块都
写着 *"This replaces any statement written within the manuscript and is the
one that we will publish."* —— 也就是说**界面版本取代正文版本**，我们改成
界面里填错，正文写得再对也没用。所以每个文本框都要认真填，能复制就别手打。

### 逐块说明

**1. Publishing policy（勾选框）**

勾上 "I have read and understood the publishing model policy"。IJDAR 是
hybrid journal，意味着**接受后**你要在"立即金色开放获取（付 APC 版面费）"
和"订阅制（读者付费，有禁售期）"之间二选一。**现在不用做这个选择，也不
产生费用**，只是确认你知道了。我们经费有限，到时候选订阅制即可。

**2. Competing interests（单选）**

选 **No, I declare that the authors have no competing interests**。
与正文 `Competing Interests` 一致（"The authors declare no competing
interests."）。

注意这里有一句提示值得留意：*"If you or your co-authors have a relationship
with this journal, including as an Editorial Board Member, Guest Editor, or
in another role, you must declare it."* —— 你们三位都是学生，与 IJDAR 编委
没有关系，所以选 No 是正确的。**但请确认一下导师/华老师那边没有人和这个
期刊有关联**（比如是编委或客座编辑）。若有，必须改选 Yes 并说明。

**3. Dual publication（单选）**

选 **No, ...**。这正是前面确认过的原创性问题的同一件事：此前那篇稿子
**未被录用**，投稿被拒不构成发表；且现在**不在任何刊物审稿流程中**。
所以"结果/数据/图是否已在别处发表或在别处审稿"的答案是 No。

**4. Authorship（勾选框）**

勾上 "I confirm the corresponding author has read the journal policies..."。
这不是形式主义——它要求通讯作者真的读过期刊的作者责任政策。链接就在旁边，
花两分钟扫一眼再勾。

**5. Third party material（单选）→ 见下方专段**

**6. Data availability（单选 + 文本框）**

- 问题 "Have you used or generated research data in this study?" 选
  **`Yes. I used or generated research data in this study.`**
  我们确有一手数据：769 条 QC 后样本、六通道 mask、200 张参考图 cache、
  150 对人工评分。**不能选 No** —— 那句 No 写的是"本稿未报告数据生成或
  分析"，与实际相反。
- 随后出现的文本框，粘贴 `DECLARATIONS.md` 里的 **Data Availability**
  整段（含仓库路径、外部参考图来源与 CC BY-NC 署名、以及"可向通讯作者
  索取"那句）。注意：前面我已经把这段里的反引号去掉了，现在可以直接复制。

**7. Acknowledgements（文本框，可选）**

界面提示 "If you do not have anyone to acknowledge, leave it blank."，
我们**有**内容，粘贴这一句：

```
The authors thank Chengcheng Wan for project supervision.
```

界面还提示 *"Make sure you get permission from those mentioned in the
acknowledgements section."* —— 请跟万老师（Chengcheng Wan）说一声要写进致谢。

**8. Research funding（单选）**

选 **No, this research did not receive funding.** 与正文的
*"No external funding or grant number is recorded."* 一致，正文无需改动。
详见下方专段。

### 第 5 块：Third party material —— 这是个有分量的选择

界面问：*"Does your manuscript contain any material from third parties?"*

两个选项，我建议选 **第一项 No**：

> No, all of the material is owned by the authors and/or no permissions are
> required.

**为什么不能选第二项：** 第二项的原文是 *"the manuscript contains third
party material and **obtained permissions are available on request** by the
Publisher."* 它要求我们**已经取得了许可**并能应出版商要求出示。我们
**没有取得书面许可**（你决定不发那封邮件），所以选第二项等于作不实陈述。

**选 No 的依据：** 选项文案里的 "and/or no permissions are required" 正是为
我们这种情况设计的——材料不归作者所有，但不需要许可。我们的理由：

- 图中书法原作出自欧阳询（唐）、王羲之（东晋），**作品早已进入公有领域**；
- Calli-Tongji 以 CC BY-NC 4.0 授权的是**数据集**（扫描件与标注），不是
  这些古代作品；
- CC BY-NC 许可本身就预先授予了非商业复制权，**不需要另行"申请"许可**
  （我们做的署名已经满足许可要求，署名保留在正文与图题注里）；
- 我们只复现了少量**降分辨率缩略图**，未再分发数据集。

**残余风险要说清楚：** 如果编辑部接受后在生产环节专门追问这批图的来源，
届时再补那封邮件也不迟（那时你有的是编辑的明确要求）。若你不愿承担任何
残余风险，唯一的彻底办法是把 Fig. 1(a)、Fig. 3(c)、Fig. 5 里的参考图换成
自有语料——但这两张图的意义恰恰是"跨书体对照"，自有语料没有王羲之行书，
换掉会失去论证点。**我的建议是保持现状，选 No。**

### 第 8 块：Research funding —— 已定：选 No

界面问：*"Is the research described in this manuscript supported by
funding?"*

**作者已决定（2026-09-19）：选 `No, this research did not receive
funding.`** 理由：该大创项目没有 grant number，属于校内孵化项目，未设外部
资助。这一选择**与正文完全一致**，因为正文的 Funding 声明本来就写着
*"No external funding or grant number is recorded."*

因此：

- 本项选 **No**；
- **正文一字不用改**，无需重新编译，**无需重新上传 zip**；
- 若选了 No，系统不会再追问出资方名称与编号，跳过即可。

> 留档备查（不改动，仅记录推理）：作者曾为租 GPU 索取发票，理论上存在从
> 项目账报销的可能，那样严格说应算受资助。作者确认项目无编号、按 No 处理，
> 且与正文陈述一致，故按 No 执行。

---

## 第 7 步：Review 标签页（提交前最后检查）

系统会生成一份 PDF 预览。**逐项核对这几点**：

- [ ] 标题、三位作者姓名与顺序正确
- [ ] 通讯作者标记在 Xiaofan Liu 上
- [ ] 摘要完整（四段都在，没被截断）
- [ ] 6 个关键词都在
- [ ] 正文 20 页，参考文献是数字引用
- [ ] 图 1、2、3 等图片都显示正常（不是空白框）
- [ ] **Declarations 页八块都处理了**：两个勾选框已勾，Competing interests
      选 No，Dual publication 选 No，Third party material 选 No，
      Data availability 选 Yes 并**粘贴了整段声明**，Acknowledgements 已填，
      Research funding 选 No
- [ ] **Data availability 的文本框不是空的**（选了 Yes 却没填文本 =
      最终文章里这条声明会缺失）
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
2. **文章类型选成 Survey** → 综述与研究论文的评审预期完全不同；我们是一手
   研究，必须选 `Research`。
3. **传错 zip** → 别传 109 个文件那个协作包。
4. **声明字段留空或与正文不一致** → 界面里的才会进终版，必须照抄
   `DECLARATIONS.md`。
5. **ORCID 末位 `X` 当成数字打错** → 填完核对一遍。
6. **别在正文里加 `\orcid{}`** → 我们的 `sn-jnl.cls` 缺少 `Orcidlogo.eps`，
   会导致系统编译失败、投稿当场挂掉。ORCID 走界面填就够了。
7. **系统编译出 `[?]`** → 多数是只编译一遍，刷新看看；持续存在就告诉我。

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
