# 2026-09-05 论文主体文字修订说明

本轮保留原有“参考条件下的结构评估 → C1–C4 → RQ1–RQ4 → 实验与边界”的论证主线。没有新增实验结果、改变模型排序、改写数据规模，也没有新增文献条目。标题、作者信息、伦理与数据可用性声明保持原样；这些声明仍需作者按照原投稿检查表确认。

本轮应用 `nature-polishing`：algorithmic / English / generic（实际目标期刊仍为 IJDAR）。精修范围为标题与摘要检查、引言、相关工作、综合讨论及结论；没有将视觉品质目标解释为修改投稿定位或宣称达到某个期刊、会议的录用标准。

## 已修改的文件

| 文件 | 主要改动 | 对读者的作用 |
|---|---|---|
| `manuscript.tex` | 压缩摘要背景，明确三类证据的不同评估对象，保留全部数值 | 第一段直接交代“字能认出来，但局部结构仍有差异”的问题；不把人类对分数的评价写成对诊断输出的验证 |
| `sections/01_introduction.tex` | 聚焦动机，整理 C1–C4/RQ1–RQ4，压缩贡献项和 Fig. 1 图注 | 保留原架构，同时减少长句、重复结果及“我们是第几个贡献”的自我说明 |
| `sections/02_related_work.tex` | 拆分 Stroke-Seg 等密集长句，强化任务区分与引用归属 | 更容易区分识别、风格分类、笔画实例分割和当前方向通道比较；没有贬低先前多标签方法 |
| `sections/07_discussion.tex` | 将结果解释与证据边界分开，修正方向标签与端点的逻辑关系 | 解释“分数”和“诊断”为何需要不同证据，清楚交代实验实际验证到了哪一层 |
| `sections/08_conclusion.tex` | 按 RQ 压缩收束，保留数值和局限，删除泛化的等效与测量优越性措辞 | 结尾更清晰，也减少审稿人对论断强度的质疑 |

## 关键科学措辞修正

1. **删除过于绝对的文献定位。** 原摘要的 `None returns ...` 容易被读成“没有任何相关方法能输出这类结果”。现在从任务缺口出发，说明识别、风格分类与生成的目标不直接评价本文的方向与空间差异；原引用全部保留。

2. **区分跨风格差异与书写错误。** Fig. 1 的楷书—行书例子可以展示结构差异，但不能直接作为某一方写错的依据。引言现在明确这是比较任务的示意，随后再解释哪些全局变化被补偿、哪些局部差异被保留。

3. **不把数值接近写成统计学等效。** `equivalent` / `nearly equivalent` 改为 `nearly identical association in this cohort`。保持 direct-ink ASDS 的相关系数差值 `Δρ = 0.0004` 不变，但不暗示做过预先设定等效界值的等效性检验。

4. **修正方向标签交换的反事实论述。** 方向标签置换若保持 union silhouette 不变，ASDS 不变；它也不会必然改变独立的 endpoint mask。现在分别说明方向比较、局部归因与端点通道的关系，删除原文“会改变 every ... endpoint ... output”的错误。

5. **准确描述对齐实验。** `preserving 11.189 additional points ...` 改为“结构惩罚增加 11.189 分”。增加惩罚是观测结果，不能独立证明测量更忠实；讨论保留局部编辑触发质心重拟合的解释。对于更宽搜索，注明它同时采用更粗采样，因而当前对比没有隔离搜索范围这一因素。

6. **明确各实验的验证层次。** 摘要注明 RQ2/RQ4 使用 cached masks；讨论说明扰动掩膜直接进入比较阶段，没有对扰动图像重新运行解析器。RQ3 的主分数比较使用人工标注掩膜，direct-ink 对照则绕过解析，因此不能概括为“所有分数都由标注掩膜计算”。

7. **保留 ASDS 的回顾性边界。** `ρ = 0.556` 始终为 retrospective development；`ρ = 0.540` 始终为 character-grouped internal validation。特征设计已经看过评分，因此没有提升为外部、前瞻性验证；out-of-fold ASDS 相对 coverage-aware score 的优势仍未解决。

8. **避免把本文的解析需求泛化到所有系统。** “任何诊断系统都需要该 parser”的含义收窄为“本框架利用 parser 提供轮廓本身没有的方向与端点证据”。这保留了项目核心价值，同时避免排除其它可能的诊断表示。

## 术语表

| 统一用语 | 首次定义/含义 | 原文变体或容易混淆之处 | 本轮决定 |
|---|---|---|---|
| reference-conditioned structural assessment | 相同字符的参考图条件下，比较结构差异 | reference-based assessment | 主体表述继续采用前者；保留原关键词 |
| candidate / learner image | 待评价书写图像 | 软件合同中的 `user` | 图内继续 candidate；正文沿用 learner；不修改软件标识 |
| direction-family channel | 五个可独立激活、可重叠的方向家族通道 | direction mask / stroke instance | 不写成笔画实例，也不暗示恢复书写顺序 |
| endpoint channel / endpoint mask | 第六个、独立的端点输出 | 软件历史字段 `keypoint` | 科学正文只使用 endpoint |
| constrained similarity registration | 受限的全局相似变换搜索 | bounded registration / alignment | 术语沿用；结论同时写清比较基线与残余敏感性 |
| frozen production score | 既有冻结的生产评分 | production score | 不称其为本轮重新拟合的模型 |
| coverage-aware score | 只对有效方向通道等证据按规则评分的审计变体 | active-channel score | 统一沿用 coverage-aware score |
| aligned spatial-distribution similarity (ASDS) | 对齐轮廓的空间分布相似度 | ASDS scalar / silhouette score | 首次展开；解释保持为 silhouette descriptor |
| annotated-mask-union ASDS | 五个人工标注方向掩膜的并集作为输入 | parsed union | 人类评分队列中避免写成 parser prediction |
| direct-ink ASDS | 直接阈值化原始墨迹作为输入 | equivalent / interchangeable | 使用“当前队列中相关性近乎相同”，不声称统计等效 |
| character-grouped internal validation | 按字符分组的内部验证 | out-of-fold / external validation | 保留 out-of-fold，明确不构成外部确认 |
| exact-cell localization | 要求一个预测格与一个真值格精确匹配的指标 | exact-region / exact-one-cell | 延续冻结指标，不把跨格真值失败直接等同于毫无定位作用 |

## 投稿前仍需明确的事项

- **优先级最高的是证据强度，而非更多形容词。** ASDS 在现有队列的关联有吸引力，但无需通过包装成“已验证通用美学评分”来抬高贡献；目前最可辩护的组合仍是可检查的多标签表示、评分语义审计和失效分析。
- **固定 ASDS 之后的新队列验证仍未完成。** 如未来补充新作者、新字符、新评分者，应保持当前特征与权重冻结；本轮没有补造任何独立结果。
- **端到端证据尚未闭环。** RQ1 验证解析，RQ2/RQ4 验证缓存掩膜上的比较与诊断，RQ3 主要验证标注掩膜的评分。这些结果不能直接相加为“部署流水线已经完成人类验证”。
- **搜索范围与采样密度未分离。** 当前 wider-search 结果支持“这一个更宽且更粗的实现没有改善指标”，不能支持普遍的“更大范围无益”。
- **多标签交叉点指标与多格定位指标仍可补强。** 当前交叉点主要是定性证据；固定单格指标会惩罚跨格真值。新指标应作为透明补充，不能覆盖冻结结果。
- **模型排序依赖初始化协议。** 三种架构的预训练与初始化不同，因此排序属于当前训练协议下的比较，不能单独归因为架构设计。
- **人类评分者中两人为作者、单评分者可靠性偏低、队列规模和单来源限制仍如实保留。** 语言润色不能消除这些研究设计限制。

## 验证记录

- 仅修改上述五个论文源文件及本说明，没有提交或推送。
- 所有原有引用键保留，没有新增引用键。
- 对五个源文件进行数值 token 对比，原有非引用数值无删除、无变更、无新增。
- TeX 花括号配对检查和 `git diff --check` 通过。
- 摘要约 206 词（将每个行内数学表达式记为一个词），低于原 README 的 250 词上限。
- 五个主体文件净减少约 107 个词（剔除主要 TeX 命令与数学公式后的近似统计）；新增讨论内容由引言、摘要和结论的压缩抵消。
- 完整 LaTeX 编译和新版插图的逐页视觉检查由整合流程统一执行，避免并行写入同一个构建输出。
