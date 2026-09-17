# SNAPP 投稿页面填写指南（2026-09-17）

对照投稿系统 `Files` 页面的每个槽位，下面是应该上传/粘贴什么。所有文件都
在本目录 `paper/releases/2026-09-17-submission/` 下。

## 一、按槽位对应

| 系统槽位 | 上传什么 | 说明 |
| --- | --- | --- |
| **Manuscript file** | `OneStroke2026_manuscript_latex.zip` | LaTeX 源码包，33 个文件、2.8 MB，主文件是 `manuscript.tex` |
| **Supplementary material** | `OneStroke2026_ESM_1_submission.pdf` | 4 页 Online Resource 1：表 S1–S4 + 注 S5–S6 |
| **Related files** | `OneStroke2026_cover_letter.pdf` | 给编辑的投稿信；拿到图片许可回复后再加上许可邮件 |
| **Details / Authors / Declarations 标签页** | 粘贴 `DECLARATIONS.md` 里的文本 | 界面里填的才会进最终版，正文里的声明不算 |
| **Figures and tables** | 初始阶段可留空 | 系统写明"接受后再提供高分辨率原图" |

系统对 Manuscript file 的要求是"LaTeX 文档连同图表压缩成 zip"，并会
**自己编译成 PDF 送审**。所以这个 zip 我做成了只含编译必需文件：

```text
manuscript.tex                  <- 主文件
manuscript.bbl                  <- 预生成的参考文献（关键）
references.bib
sn-jnl.cls                      <- Springer 模板类
sn-basic.bst                    <- 编号引用样式（类文件自动调用）
sections/*.tex                  <- 8 个正文章节
tables/*.tex                    <- 9 个正文表 + 4 个补充表
figures/.../*.pdf               <- 正文实际引用的 7 张图
```

两个刻意的设计，都是为了"别让编译环境坑我们"：

1. **包内只有根目录一个 `.tex`**。`sections/` 和 `tables/` 里都是片段而不是
   完整文档，`ESM_1.tex` 也**不放进来**（它是独立文档，会干扰系统识别主
   文件，而且它本身要走 Supplementary 槽位）。打包脚本会强制校验这一点。
2. **带上 `manuscript.bbl`**。很多投稿系统不会自动跑 bibtex。我实测过：
   在干净目录里解压后，即使完全跳过 bibtex，只要跑两遍 pdflatex，71 处引用
   也 100% 解析、0 个 undefined、同样是 20 页。带 bibtex 的正常流程也验证过。

## 二、我在干净目录里做过的验收

把 zip 解压到空目录后实测（不是在工作区里测的）：

| 场景 | 结果 |
| --- | --- |
| pdflatex + bibtex + pdflatex×2 | 20 页，0 Overfull，0 undefined |
| 跳过 bibtex，只跑 pdflatex×1 | 20 页，但 47 处引用暂时显示 `[?]`（正常，需要第二遍） |
| 跳过 bibtex，pdflatex×2 | 20 页，0 undefined，71 处数字引用全部解析 |

所以只要系统跑两遍或以上（基本都这样，标准做法是 latexmk），就是干净的。

## 三、这一轮为"可提交"新做的事

1. **补了一条声明**：正文加了 `Consent for Publication`（Not applicable），
   这是 Springer 标准声明清单里原先缺的一项。加了之后稿子一度变成 21 页，
   我通过精简 Funding 里一句冗余表述、并把参考文献条目间距设为 2pt，
   重新压回 **20 页**，没有删任何研究内容或数值。
2. **投稿信** `OneStroke2026_cover_letter.pdf`（2 页，字体全嵌入）。
   里面写清了：特刊匹配点、四项贡献、原创性声明、第三方图片许可说明、
   20 页/228 词摘要/6 个关键词的格式合规说明、以及声明汇总。
3. **声明粘贴文本** `DECLARATIONS.md`，与正文逐字一致。

## 四、投稿前需要你们处理的 3 件事

这几件我做不了，但都会直接影响投稿：

1. **三张证件照 + 简介确认**。IJDAR 作者须知明确要求 50–100 词简介和护照
   尺寸黑白照。简介已写好（`paper/AUTHOR_BIOGRAPHIES.md`），需要三位本人
   确认措辞并提供照片。注意冯缘那份我已经改成女性代词。黑白照怎么交、
   交什么规格，见 `AUTHOR_BIOGRAPHIES.md` 末尾的说明。

2. **跟院里确认伦理声明措辞**。现在写的是 "Not applicable" 且未引用校内
   规定。若华师大要求写具体的豁免依据，告诉我改哪里。

3. **原创性声明确认**。投稿信里写了"未发表、未他投、没有需要申报的同作者
   会议论文"。请确认这与事实一致；如果去年那个项目有对外发表的论文，这
   一段必须改。

## 四之二、关于第三方图片：已按你的要求处理

投稿信里原先那段"第三方图片与许可"已按你的要求**整段删除**，也不再主动向
编辑部提出许可事宜。需要你知道的是：

**撤掉投稿信里那段，不改变底层权利状况，只是不再主动提请编辑注意。** 权利
链条本身比我最初判断的乐观：

- 图中的书法原作出自欧阳询（唐）与王羲之（东晋），**作品本身早已进入公有
  领域**，全球范围内均无版权；
- Calli-Tongji 以 CC BY-NC 4.0 授权的是**数据集**（扫描文件与标注），不是
  这些古代作品；
- 论文只复现了少量**缩略、降分辨率**的示例图并完整署名，未再分发数据集；
- 美国判例（Bridgeman v. Corel, 1999）认为对二维公有领域作品的忠实翻拍
  不产生新版权；其他法域依据不一，这是残余不确定性的来源。

所以实际风险偏低，且完整署名已经满足 CC BY-NC 的核心要求——署名与许可声明
仍保留在正文的基金/数据可得性声明与各图题注里，这部分**没有删、也不能删**。

如果编辑部在接受后的生产环节真的问起，届时再发那封邮件也来得及（那时你有
的是编辑的明确要求，比现在主动发函更有据可依）。若你不希望承担任何残余风险，
唯一的彻底办法是把 Fig. 1(a)、Fig. 3(c)、Fig. 5 里的参考图换成项目自有语料
——但 Fig. 1(a) 与 Fig. 3(c) 的意义正是"跨书体对照"，自有语料没有王羲之行书，
换掉会失去这个论证点。我的建议是保持现状。

## 五、可选但建议

- **数据归档**：把 QC 契约、两个 split、769 样本与六通道 mask 存到
  Zenodo/Figshare 拿一个 DOI（第三方参考图不能放进去）。拿到 DOI 我加进
  Data Availability。
- **图 2 的 105 dpi 局部放大图**：这是全篇唯一低于 Springer 300 dpi 门槛的
  位图（`figure2_channel_definition.pdf` 里那个放大交叉块）。接受后要交
  高清原图，建议现在就用本地 `data/legacy_gt_v1/output_img/33/18/mask_*.npy`
  从 GT 重新裁一张。你说一声我就改。
- **图 1 题注的前向引用**：题注里提到了 Fig. 3，使首次提及顺序变成 1、3、2。
  改成章节引用即可，一行改动。

## 六、两个 zip 的区别

| 文件 | 用途 |
| --- | --- |
| `OneStroke2026_manuscript_latex.zip` | **投给 SNAPP 用**，33 文件、精简、只含编译必需件 |
| `OneStroke2026_online_latex_submission.zip` | 给你们三人 + Claude 在 Overleaf 上协作用，109 文件、含绘图脚本与内部文档 |

别把 Overleaf 协力包传成投稿包——里面有协作说明和历史修订文档，会让出版方
困惑。
