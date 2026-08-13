# “一笔成章”项目工作总整理

> 更新时间：2026 年 8 月 13 日
>
> 项目仓库：<https://github.com/LiuXiaofan-0321/OneStroke2026>
>
> 本地工程：`C:\University Courses\大创项目\model_module`
> 旧项目参考：<https://github.com/Mmrliu-gooooood/OneStroke>

## 1. 文档用途

本文档汇总从 2026 年 7 月启动模型模块以来，已经完成的工程、数据、模型、
课程包、评分、反馈、HTTP 联调和论文实验工作，并列出当前尚未完成的任务。

它可用于：

- 项目负责人换设备或换账号后的继续开发；
- 团队内部交接和分工；
- 向指导老师、博士后或答辩评委汇报；
- 软件开发同学理解模型能力和接口；
- 继续撰写 IJDAR 方向论文；
- 避免重复训练、重复标注或错误使用实验数据。

本文档以仓库和正式实验产物为准，不以早期计划中的预计状态为准。

---

## 2. 项目最终目标

“一笔成章”希望完成一个面向汉字书写与书法练习的软件系统。模型侧承担三类
任务：

1. **笔画结构分割**
   - 输入一张完整汉字 RGB 图片；
   - 输出五个方向类别和一个关键点通道；
   - 支持交叉、粘连、端点和多方向重叠区域。

2. **课程参考字结构比较**
   - 用户先选择课程和目标字；
   - 系统将用户书写与同课程、同字参考进行限制性对齐；
   - 输出“参考结构匹配度”和局部差异证据。

3. **可解释修改建议**
   - 根据重心、大小、关键点、方向区域和局部差异生成规则建议；
   - 可选调用文本大模型润色；
   - 不能让大模型修改分数、虚构笔顺或声称专家审美结论。

当前系统的科学定位是：

> 低资源条件下的、参考字条件化的汉字笔画结构分析系统。

当前不能定位为：

- 通用书法审美评分器；
- 任意书家、任意字的字体鉴定器；
- 笔顺恢复系统；
- 已经完成未见书写者验证的通用模型；
- SAM2 或新型分割架构论文。

---

## 3. 当前总体架构

```text
用户选择课程和目标字
        │
        ├── target_char 已知，因此课程模式不需要 OCR
        │
        ▼
上传/绘制完整汉字 RGB 图
        │
        ▼
SegFormer-B2 六通道分割
        │
        ├── vec1
        ├── vec2
        ├── vec3
        ├── vec4
        ├── vec5
        └── keypoint
        │
        ▼
从课程库选择同字参考 mask
        │
        ▼
受限全局对齐
  平移 + 等比缩放 0.80–1.20 + 旋转 ±3°
        │
        ▼
结构一致性评分
  方向 Dice + 墨迹 IoU + 关键点容忍 F1
        │
        ▼
结构化证据与局部区域
        │
        ├── 规则化中文建议（始终可用）
        └── 可选文本 LLM 润色（失败时回退规则）
        │
        ▼
HTTP API → Java 业务后端 → 前端展示
```

### 3.1 三个必须区分的层次

#### 基础 B2 分割模型

- 只负责六通道结构解析；
- 不读取字体或书家 ID；
- 基础模型本身不是字体条件模型；
- 模型卡中的 `style_conditioning=false` 是正确的。

#### 课程参考条件化封装

- 根据 `course_id + target_char` 选择同字参考；
- 使用同一个 B2 分割器处理用户图；
- 字体差异来自参考字选择和结构比较，不是每个字体训练一个 B2；
- 课程分析接口可以声明 reference-based `style_conditioning=true`。

#### 论文验证管线

- 用真实参考 mask、受控扰动、对齐消融、人工评分验证结构分数；
- 不改变线上 B2 checkpoint；
- 不为追求漂亮数字临时修改对齐范围或评分公式。

---

## 4. 团队分工和历史任务

### 刘小凡

- 模型工程架构；
- SegFormer-B2 训练、消融、定型和发布；
- 关键点诊断；
- 课程参考库和结构评分；
- AI 建议约束；
- HTTP 模型服务和开发联调；
- 论文实验设计、统计分析和论文骨架；
- 数据恢复与研究完整性管理。

### 张荣昊

早期“任务 1、3”已经完成：

1. 审核 54 个异常样本；
2. 重测 U-Net 基线；
3. 提供 checkpoint 和指标记录。

复核文档：

```text
docs/zhang_ronghao_delivery_review_2026-07-27.md
```

注意：这里的“张荣昊任务 1”与现在论文计划中的“Task 1 主分割正式比较”
不是同一个任务。

2026 年 8 月 13 日补充：840 仅表示六通道文件完整。统一语义 QC 又排除了
12 个原图/GT错配和 59 个完全重复非主实例，正式训练人口为 769 个
QC-clean 独立样本。新版论文 Task 1 指令见：

```text
docs/zhang_ronghao_task_1_3.md
```

### 高怡然/书法与美术成员

规划职责包括：

- 困难样本和参考字人工质量复核；
- 结构建议语义复核；
- 后续真实书写样本和手机拍摄样本复核。

### 开发同学

- 已完成前端主体开发；
- 已加入课程/字体选择页面；
- 已与模型 HTTP 服务完成一次真实两端联调；
- 能接收评分、反馈、分割图片和 mask 资源；
- 业务后端的长期部署、存储、权限和任务管理仍需继续工程化。

---

## 5. 工程基础建设

已新建独立模型工程，不继承旧项目训练框架。旧仓库仅作为以下内容的来源：

- 原始数据；
- 单笔画采集方式；
- 标签生成逻辑；
- 旧 U-Net 结构和权重参考。

### 5.1 当前主要入口

```text
train.py       训练
eval.py        固定划分评测
infer.py       单图推理和资源导出
```

### 5.2 Python 包

```text
src/onestroke_model/
```

已包含：

- 数据审计和划分；
- U-Net；
- SegFormer 六通道封装；
- 多标签损失；
- 阈值校准；
- 原图尺寸恢复；
- 六通道 mask 和 overlay 导出；
- 参考字导入与 mask cache；
- 受限对齐和结构评分；
- 课程练习分析；
- 规则反馈和可选 LLM 调用；
- HTTP API；
- 论文实验和统计工具；
- 数据恢复和完整性校验。

### 5.3 训练器能力

- Python 3.11+；
- PyTorch；
- AdamW；
- 编码器/解码器分层学习率；
- AMP 混合精度；
- warmup + cosine；
- early stopping；
- 可复现随机种子；
- 训练/验证日志；
- best checkpoint；
- 独立阈值校准；
- 测试集只做最终评测。

### 5.4 已修复的关键问题

SegFormer smoke test 首次在 AMP 下触发：

```text
binary_cross_entropy is unsafe to autocast
```

已修复 Boundary Loss 的 AMP 安全性，相关提交：

```text
d560a68 Fix boundary loss under AMP
```

Hugging Face/Transformers 兼容问题也已处理：

```text
transformers>=4.41,<5
```

原因是 AutoDL 当时的 PyTorch 2.3 与 Transformers 5.x 不兼容。

---

## 6. 数据工作

## 6.1 第一次数据审计

旧数据目录审计结果：

| 项目 | 数量 |
|---|---:|
| 字符目录 | 43 |
| 样本目录 | 894 |
| 完整六通道样本 | 840 |
| 缺失标签样本 | 54 |

正式文件：

```text
artifacts/data_audit/manifest.csv
artifacts/data_audit/audit_report.json
artifacts/data_audit/splits.csv
artifacts/data_audit/splits_report.json
```

54 个异常样本来自 `char_id=40,41,42`，每类 18 个。它们有原图和部分单笔画
资源，但缺少完整方向映射和六通道 `.npy` 标签，因此被排除，不能用模型输出
伪造标签。

## 6.2 840 份原始 GT 已找回

此前一度找不到的 840 份原始六通道 Ground Truth 已从旧项目归档中完整找回。

恢复源：

```text
C:\University Courses\大创项目\tmp\OneStroke-main.tar.gz
```

归档 SHA-256：

```text
b9924007099033cc8b62128dc2139ea9cb04a66a48e56c46518407677254450d
```

恢复目录：

```text
data/legacy_gt_v1/output_img/
```

验证结果：

- 894/894 manifest 样本都在归档中；
- 840/840 完整样本成功恢复；
- 所有独立 mask 都是二值布尔数组；
- 每份 `0.npy` 都与五个方向 mask 和 keypoint mask 的堆叠完全一致；
- 没有生成、猜测或修补标签；
- 200 个 SegFormer 参考 cache 没有被当成 GT。

正式报告：

```text
DATA_RECOVERY_REPORT.md
artifacts/data_recovery/manifest_resolved.csv
artifacts/data_recovery/verification_report.json
```

## 6.3 语义 QC 与正式训练人口

文件完整性检查之后又完成了独立语义 QC：

```text
840 个完整 GT
- 12 个原图/GT错配
- 59 个完全重复非主实例
= 769 个 QC-clean 独立样本
```

两类排除项没有重叠。原标准 split 不存在跨 train/val/test 的 exact duplicate
组，所以旧 B2 的 `0.9610` 不是被精确 train→test 重复直接抬高；但训练仍受到
mismatch 和重复加权影响，正式论文比较必须重跑。

固定制品：

```text
artifacts/data_qc/manifest_qc_v1.csv
artifacts/data_qc/dataset_qc_exclusions_v1.csv
artifacts/data_qc/standard_splits_qc_v1.csv
artifacts/data_qc/character_disjoint_splits_qc_v1.csv
artifacts/data_qc/dataset_qc_report_v1.json
```

## 6.4 原始标签来源

旧项目的采集和标签生成链路为：

1. iPad/采集工具导出完整字图；
2. 同时导出人工逐笔书写的单笔画图；
3. 根据字符专属 `STROKE_VECTOR_MAP` 把单笔区域映射到五个方向通道；
4. 提取关键点区域；
5. 保存五个方向 mask、keypoint mask 和六通道堆叠 mask。

因此 840 份标签来自人工分笔采集和确定性映射，不是神经网络预测结果。

## 6.5 标准划分

历史 B2 v1 与 U-Net 基线使用：

```text
train / val / test = 600 / 120 / 120
```

该划分按固定样本序号组隔离，但 40 个字符会同时出现在三个集合中。

它适合：

- 比较固定数据分布下的分割性能；
- B0/B1/B2 消融；
- 发布工程模型。

正式论文主基准保留原分配后应用 QC，变为：

```text
train / val / test = 530 / 119 / 120
```

它不等于：

- character-disjoint 泛化；
- unseen-writer 泛化。

## 6.5 Character-disjoint 划分已冻结

论文用严格按字符隔离的划分已经准备完毕：

| 划分 | 字符数 | 样本数 |
|---|---:|---:|
| Train | 28 | 588 |
| Validation | 6 | 126 |
| Test | 6 | 126 |

三个集合字符交集为零。

冻结 SHA-256：

```text
eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e
```

文件：

```text
artifacts/paper_ijdar/character_disjoint/splits_character_disjoint.csv
artifacts/paper_ijdar/character_disjoint/character_disjoint_split_report.json
artifacts/paper_ijdar/character_disjoint/character_disjoint_execution_plan.json
configs/paper_ijdar/
```

当前状态是“管线和配置已准备，尚未正式训练”。该划分不得因看到模型结果而修改。

## 6.6 困难样本

已经完成：

- 生成 50 个困难样本候选；
- 生成联系图；
- 前 20 个高优先级样本完成困难类型、reviewer 和 keep 人工复核；
- 保留交叉、粘连、端点、线宽、背景和风格等字段。

文件：

```text
artifacts/data_audit/hardset_candidates.png
artifacts/data_audit/hardset_template.csv
reviews/hardset_review.csv
reviews/hardset_review_前20行初审完成.csv
```

当前限制：

- 这一步完成了高优先级样本复核；
- 尚未形成完整、冻结并用于 U-Net/B2 对比的正式困难测试集；
- 不能把人工候选复核写成“困难集性能已经完成”。

---

## 7. U-Net 可信基线

已将旧 U-Net 接入新的数据、训练、阈值和评测框架。

正式结果：

| 指标 | U-Net |
|---|---:|
| 五方向 Macro Dice | 0.891350 |
| Macro IoU | 0.804875 |
| Keypoint F1 | 0.753010 |
| Boundary F1 | 0.738529 |

交付：

```text
configs/train_unet_rebaseline_v1.yaml
checkpoints/unet_rebaseline_v1/best.pt
docs/unet_rebaseline_report_2026-07-12.md
```

该结果替代旧项目约 85.2% 的自定义准确率，成为当前可信基线。

---

## 8. SegFormer-B2 训练与消融

## 8.1 模型定义

- 主干：SegFormer-B2；
- 预训练：ImageNet/ADE20K；
- 输入：RGB，白底 letterbox 到 `512×512`；
- 输出：六通道 logits；
- 激活：六个独立 Sigmoid；
- 禁止 Softmax；
- 通道允许重叠。

固定通道顺序：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

## 8.2 三组消融

| 实验 | 关键设计 | Macro Dice | Macro IoU | Keypoint F1 | Boundary F1 |
|---|---|---:|---:|---:|---:|
| U-Net | 重测基线 | 0.891350 | 0.804875 | 0.753010 | 0.738529 |
| B0 | 方向加权 BCE+Dice；关键点 BCE+Dice | 0.955282 | 0.914415 | 0.713028 | 0.808364 |
| B1 | 关键点改为 Focal+Dice | 0.955414 | 0.914657 | 0.713854 | 0.807672 |
| **B2** | B1 + 0.2 Boundary Loss | **0.961049** | **0.925051** | **0.715935** | **0.834753** |

结论：

- B0 证明 SegFormer-B2 对五方向分割有效；
- B1 的 Focal 配置只带来很小的关键点变化，不能宣称显著有效；
- B2 的边界损失明显改善方向分割和 Boundary F1；
- B2 被选为 v1 冻结交付模型。

相对 U-Net：

- Macro Dice 提升约 **6.97 个百分点**；
- Boundary F1 提升约 **9.62 个百分点**；
- 严格 Keypoint F1 下降约 **3.71 个百分点**。

## 8.3 B2 各通道结果

| 通道 | Dice | IoU |
|---|---:|---:|
| vec1 | 0.962339 | 0.927412 |
| vec2 | 0.954505 | 0.912970 |
| vec3 | 0.960956 | 0.924846 |
| vec4 | 0.959596 | 0.922331 |
| vec5 | 0.967847 | 0.937697 |
| keypoint | 0.715935 | 0.557553 |

## 8.4 关键点问题的复核

严格逐像素关键点 F1 较低，但距离容忍指标显示它主要是小区域边界偏移：

| 允许偏差 | Keypoint F1 |
|---|---:|
| 0 px | 0.7160 |
| 1 px | 0.8997 |
| 3 px | 0.9284 |
| 5 px | 0.9354 |

测试集 120 个样本中：

- 没有完全漏掉预测的样本；
- 严格 F1 低于 0.5 的样本只有 1 个；
- 5 px 容忍 F1 低于 0.8 的样本有 4 个。

因此：

- 严格 F1 仍保留为正式分割指标；
- 下游使用关键点中心坐标时，可采用 3–5 px 容忍；
- 不需要为了关键点立即推翻 B2 主体。

## 8.5 冻结发布

模型版本：

```text
segformer-b2-v1
```

checkpoint：

```text
checkpoints/segformer_b2_v1/best.pt
```

大小：

```text
328,624,482 bytes
```

SHA-256：

```text
64df27aafc0eeecc07c0ac52c6ff00eef6b290ae7baf964cd5cf786262f395ce
```

最佳 epoch：

```text
71
```

发布目录：

```text
releases/segformer_b2_v1/
```

包含：

- 模型清单；
- schema；
- 测试指标；
- 验证集阈值；
- 关键点容忍指标；
- B0/B1/B2 消融汇总。

## 8.6 固定阈值

阈值仅在验证集校准：

| 通道 | 阈值 |
|---|---:|
| vec1 | 0.9108889 |
| vec2 | 0.8713334 |
| vec3 | 0.9108889 |
| vec4 | 0.9306667 |
| vec5 | 0.9306667 |
| keypoint | 0.2582222 |

---

## 9. SAM2 和云端/端侧双模型路线

早期规划是：

```text
SegFormer-B2 主分割
  + SAM2 辅助边界/实例教师
  + 云端高精度模型
  + 端侧轻量学生模型
```

当前真实状态：

### 已完成

- SegFormer-B2 云端教师候选；
- 完整训练、推理和 HTTP 服务；
- 参考字 mask cache；
- 结构评分。

### 尚未完成

- SAM2 微调或 LoRA 实验；
- SAM2 边界教师；
- SegFormer-B0/MobileNetV3 蒸馏；
- ONNX；
- INT8 QAT；
- 移动端内置模型；
- 云端/端侧双阶段结果融合。

当前不应继续把 SAM2 作为近期主线，原因是：

- 840 样本规模对完整 SAM2 微调仍偏小；
- 当前论文重点已经转向结构表示、对齐、评分和可解释验证；
- 新架构会扩大实验矩阵并消耗时间；
- B2 已能完成产品演示和论文的基础解析任务。

SAM2 保留为后续研究方向：

- 单笔画实例教师；
- 新数据伪标签辅助；
- 边界精修；
- 参考字预处理。

---

## 10. 开源字体数据与课程包

## 10.1 调研过的数据

已调研：

- UniCalli；
- MCCD；
- Mobao/Moyun；
- Calli-Tongji。

文档：

```text
docs/open_dataset_assessment_2026-07-27.md
docs/calli_tongji_beta_reference_library.md
docs/style_reference_pilot.md
```

## 10.2 当前采用的数据

当前课程参考库采用 Calli-Tongji Beta：

- 欧阳询楷书类别：100 张；
- 王羲之行书类别：100 张；
- 共 200 张；
- 193 个唯一字符；
- 两个类别共有 7 个同字；
- 项目记录的许可证为 `CC-BY-NC-4.0`。

参考 manifest：

```text
references/calli_tongji_beta_manifest.csv
```

原始图片和模型 cache 因授权与体积原因默认不提交 Git：

```text
references/images/
references/cache/
```

## 10.3 两门课程

| course_id | 展示名 | 字数 |
|---|---|---:|
| `ouyang_xun_regular_100_beta` | 欧阳询楷书·100字练习包（Beta） | 100 |
| `wang_xizhi_running_100_beta` | 王羲之行书·100字练习包（Beta） | 100 |

配置：

```text
configs/course_packs.yaml
configs/style_registry.yaml
artifacts/course_packs/catalog.json
```

必须保留 Beta 和数据集来源描述。当前课程不能宣传为：

- 《兰亭序》专项包；
- 《九成宫》专项包；
- 欧阳询小楷；
- 某一个确定历史摹本。

如后续使用 UniCalli 或获得具体碑帖的可用授权，可另建真实作品级课程。

## 10.4 参考 mask cache

已用冻结 B2 为 200 张参考字生成六通道 cache：

```text
references/cache/segformer_b2_v1/index.json
```

cache 信息：

- 模型：`segformer-b2-v1`；
- canvas：`512×512`；
- 六通道；
- 200 个参考全部通过完整性检查；
- checkpoint SHA-256 与冻结发布一致。

重要限制：

> 参考 cache 是模型输出，只能用于参考比较，绝不能作为训练 Ground Truth。

---

## 11. 结构评分

## 11.1 当前评分公式

```text
100 × (
  0.55 × direction_macro_dice
  + 0.25 × ink_iou
  + 0.20 × keypoint_tolerant_f1_radius_3
)
```

展示名固定为：

```text
参考结构匹配度
```

不能展示为：

- 专家评分；
- 审美评分；
- 书法考试成绩；
- 风格真伪概率。

## 11.2 对齐策略

允许：

- 平移；
- `0.80–1.20` 等比缩放；
- `±3°` 旋转。

禁止：

- 非等比缩放；
- shear；
- deformable warp；
- 为了得到高分任意扭曲用户字。

## 11.3 早期 sanity check

参考图与自身比较曾得到接近 100 分，例如欧阳询“亮”对自身约 99.97。

该数字只能证明：

- cache 读取正确；
- 同一输入的分割和对齐基本一致；
- 评分链路能运行。

它不能证明：

- 泛化能力达到 99.97；
- 人类书写可以达到同样分数；
- 模型已经通过训练集外验证。

同一欧阳询“亮”输入：

- 对欧阳询同字参考约 99.97；
- 对王羲之同字参考约 9.91。

这证明参考选择会显著改变比较结果，但仍只是工程 sanity check。

---

## 12. 课程练习分析与 AI 建议

## 12.1 完整课程分析

`CoursePracticeAnalyzer` 在服务启动时加载一次 B2，并完成：

```text
图片预处理
→ 六通道分割
→ 课程同字参考选择
→ 受限对齐
→ 结构评分
→ 差异证据
→ 规则反馈
→ 输出图片和 JSON
```

主要实现：

```text
src/onestroke_model/course_packs.py
src/onestroke_model/course_practice.py
src/onestroke_model/feedback.py
src/onestroke_model/inference.py
```

## 12.2 输出资产

一次分析可生成：

```text
result.json
prediction.npz
mask_vec1.png
mask_vec2.png
mask_vec3.png
mask_vec4.png
mask_vec5.png
mask_keypoint.png
overlay.png
alignment_overlay.png
evidence.json
feedback_contract.json
llm_feedback.json       # 仅 LLM 成功时
```

## 12.3 笔画区域

系统可以从五个方向 mask 提取连通区域，输出：

- `region_id`；
- 所属方向通道；
- bbox；
- 面积；
- 重心。

前端可以按方向类别高亮，例如横向、竖向、左斜、右斜、点状/短笔等项目定义的
类别。

但它不是可靠的“逐笔实例与笔顺恢复”：

```text
stroke_order_analysis=false
```

因此不能显示：

- 第一笔、第二笔；
- 真实书写顺序；
- 一定等同于传统笔画名称的实例序列。

## 12.4 规则反馈

当前即使不接任何外部大模型，也能返回可审计的确定性建议，主要覆盖：

- 整体重心；
- 整体大小；
- 关键点关系；
- 局部方向结构；
- 参考缺失结构；
- 用户额外结构。

每条建议都来自 `evidence.json`，不是大模型凭空看图生成。

## 12.5 可选 LLM

已实现 OpenAI-compatible 文本 API 调用。LLM 接收的是受限结构化证据，不需要
视觉模型。

LLM 只能：

- 将证据改写为更自然的中文；
- 合并重复表述；
- 调整语气。

LLM 不能：

- 修改结构分数；
- 引入证据里没有的问题；
- 虚构笔顺；
- 宣称专家书法审美判断。

LLM 失败时，系统自动返回规则建议，整次 B2 分析不会失败。

当前状态：

- 规则反馈已经真实可用；
- 可选 LLM 调用代码已经完成；
- 外部服务的密钥、额度和模型名必须在服务端配置；
- 是否持续稳定返回 `ai_feedback.source="llm"` 仍应在正式部署环境复核；
- 任何密钥都不得进入 Git、前端或日志。

---

## 13. HTTP 模型服务和软件联调

## 13.1 已完成接口

```http
GET /healthz
GET /course-catalog
POST /analyze-course-practice
GET /artifacts/{task_id}/{filename}
```

实现：

```text
src/onestroke_model/http_api.py
src/onestroke_model/scripts/serve_http_api.py
docs/http_api_handoff.md
```

## 13.2 鉴权

除健康检查外，接口支持：

```http
Authorization: Bearer <ONESTROKE_API_KEY>
```

或：

```http
X-API-Key: <ONESTROKE_API_KEY>
```

并支持：

- 调用方 IP 白名单；
- 最大上传大小；
- 标准错误码；
- 受保护的结果资源链接。

`ONESTROKE_API_KEY` 是模型服务与 Java 后端之间自行生成的服务密钥，不是模型
权重，也不是 DeepSeek Key。

## 13.3 已完成真实联调

模型曾在 AutoDL RTX 4090 实例启动：

- 服务监听本地端口；
- 通过 AutoDL 公网端口映射给 Java 后端；
- 健康检查正常；
- Java/前端能够收到评分、总结、overlay 和分割资源；
- 后续已确认 `stroke_regions` 和六通道 mask 可以返回给开发侧。

注意：

- AutoDL 地址是临时实例地址，不是长期生产域名；
- 实例关机后开发侧不能继续真实请求；
- 代码和接口文档仍可继续开发，只有实时测试不可用；
- 目前没有完成长期高可用部署。

## 13.4 推荐部署链路

```text
浏览器前端
    ↓
Java 业务后端
    ↓  服务间 API Key
模型 HTTP 服务
    ↓
B2 + reference cache + scoring + rules/LLM
```

浏览器不应直接连接 GPU 模型服务。

---

## 14. 算力和部署结论

### 训练

- B2 训练建议 GPU；
- 一张 RTX 4090 或 A100 足够；
- 本项目 B0/B1/B2 已在 RTX 4090 完成；
- V100 可以训练，但速度更慢、AMP 和环境兼容需要更谨慎。

### 在线推理

- B2 可在 CPU 运行，但延迟明显更高；
- 演示和交互式使用建议 GPU；
- T4/A10/类似 16 GB 推理卡通常已足够，不需要 A100；
- 参考 cache 预先生成，对齐、评分和规则反馈可以在 CPU 执行；
- 文本 LLM 使用外部 API 时无需自建大模型 GPU。

### 端侧

当前 328 MB B2 不适合直接放入普通手机或 Web 前端。

端侧仍需：

```text
B2 教师
→ SegFormer-B0/MobileNet 学生
→ 蒸馏
→ ONNX
→ INT8
→ 端侧性能与精度复核
```

该工作尚未开始。

---

## 15. 论文方向

当前论文拟定位：

> Reference-Conditioned Multi-Label Stroke Structure Analysis for
> Low-Resource Chinese Calligraphy Practice

中文可表述为：

> 面向低资源中国书法练习的参考条件化多标签笔画结构分析

论文不是“提出一种新 SegFormer”，而是围绕以下贡献：

1. 允许重叠的五方向 + 关键点六通道表示；
2. 受限参考对齐；
3. 可解释结构一致性评分；
4. 真实参考上的受控扰动验证；
5. 对齐消融和评分语义审计；
6. 局部诊断失败分析；
7. 盲法人工结构验证。

论文目录：

```text
paper/
  manuscript.tex
  references.bib
  sections/
  figures/
  tables/
  supplementary/
```

目前实验协议、方法、已有结果、讨论和结论已写入。

---

## 16. 已完成的论文正式实验

## 16.1 Controlled Perturbation

对 200 个真实参考 mask 施加确定性扰动，隔离评分/对齐行为与分割误差。

### nuisance

- translation；
- rotation；
- scale up；
- scale down；
- compound allowed transform。

### structural

- terminal deletion；
- extra fragment；
- local fragment shift；
- direction dilation；
- direction erosion；
- keypoint shift。

主要结果：

| 扰动 | 平均绝对分数下降 |
|---|---:|
| Translation | 0.000 |
| Rotation | 5.395 |
| Scale up | 13.653 |
| Scale down | 16.356 |
| Compound | 8.143 |

结论：

- 平移可以被当前对齐完全吸收；
- 旋转仍有一定误差；
- 缩放是当前最明显的 nuisance 弱点；
- structural 扰动总体随严重度单调降低；
- scale up 和 compound 中存在裁切风险，已按 invalid 保留而非静默删除。

正式目录：

```text
artifacts/paper_ijdar/controlled_perturbation/
```

## 16.2 Alignment Ablation

比较：

```text
no alignment
current constrained
wide similarity
```

总体结果：

| 对齐 | nuisance 平均下降 | structural 平均下降 |
|---|---:|---:|
| No alignment | 38.573 | 3.677 |
| Current constrained | 8.455 | 14.865 |
| Wide similarity | 11.351 | 15.149 |

当前对齐相对 no alignment：

- nuisance penalty 减少 `30.118`；
- 95% CI `[29.506, 30.727]`；
- structural penalty 增加 `11.189`；
- 95% CI `[10.094, 12.322]`。

当前范围相对 wide：

- nuisance 结果好 `2.896`；
- wide 只多保留约 `0.284` structural penalty。

因此不继续为了漂亮结果扩大对齐范围。

正式目录：

```text
artifacts/paper_ijdar/alignment_ablation/
```

## 16.3 Structure Score Audit

发现：

- 200 个参考中 41 个至少有一个空方向通道；
- 36 个有 1 个空通道；
- 5 个有 2 个空通道；
- 没有 3 个及以上空方向通道；
- 固定五通道 Macro Dice 会给双方都为空的通道记满分。

Coverage-aware 修正：

- 平均修正约 `0.289` 分；
- 最大修正 `15.402` 分。

这说明少数样本会因空通道得到与实际活动结构无关的额外分数。

当前决策：

- production score 保持冻结；
- coverage-aware 作为 audit score；
- 不根据当前实验事后直接替换线上公式；
- 下一版本应预注册后独立验证。

正式目录：

```text
artifacts/paper_ijdar/structure_score_audit/
```

## 16.4 Cross-reference

当前参考库只支持：

- 7 个同字跨书体 pair；
- 50 个不同字 negative pair；
- 不支持同字、同书体、不同实例 pair。

结果：

| 类型 | N | 平均分 |
|---|---:|---:|
| 同字跨书体 | 7 | 20.239 |
| 不同字 negative | 50 | 9.741 |

Cliff's delta：

```text
0.84
```

结论：

- 当前分数具有一定同字结构信号；
- 样本太少，且没有同书体不同实例条件；
- 不能据此宣称通用字体泛化。

正式目录：

```text
artifacts/paper_ijdar/cross_reference/
```

## 16.5 Feedback Diagnostic

当前规则结果：

| 指标 | 结果 |
|---|---:|
| Required Recall@3 | 0.701 |
| Strict primary Top-1 | 0.582 |
| 方向通道准确率 | 0.599 |
| Missing/extra 准确率 | 0.714 |
| Exact region | 0.109 |
| Overlap region | 0.657 |
| Specificity | 0.344 |
| 中心方向措辞正确率 | 0.250 |

Exact region 失败主要来自：

- 真实扰动跨多个九宫格，但指标要求单格完全一致：53.9%；
- 方向通道错误：24.6%；
- Top-3 中没有局部 finding：20.1%。

决策：

- 不继续为提高数字过度调规则；
- Feedback 作为 secondary/exploratory 结果；
- 论文重点写失败分类和评价指标局限。

正式目录：

```text
artifacts/paper_ijdar/feedback_diagnostic/
artifacts/paper_ijdar/journal_statistics/feedback_failure_taxonomy_summary.csv
```

---

## 17. 人工结构验证

## 17.1 题目构造

从恢复的 840 个文件完整 GT 中先应用相同 QC，基于 769 个 clean 实例构建：

- 400 个自然同字不同实例候选 pair；
- 每个字符固定 10 个候选；
- 自动排除坏图、精确重复和疑似近重复；
- 从 40 个字符中选 150 个正式 pair；
- 每个字符 3–4 个；
- 分数范围分层，但评价者看不到系统分数；
- 另加 15 个隐藏重复题。

冻结文件：

```text
artifacts/paper_ijdar/expert_validation/frozen_study_v1/
```

冻结 pair SHA-256：

```text
810d35e4e4bd0208de9608054daabaecc3613859f3a34c5a16e5141e266d8e66
```

开始真人评分后，题目、图片、顺序和 blinded ID 均未修改。

## 17.2 三位评价者

每人：

- 165 道题；
- 150 道正式题；
- 15 道隐藏重复题；
- 1–5 分结构相似度；
- 未看到模型分数和重复题映射。

评价者自报背景：

- E01：书法教师，学习 1 年、教学 1 年；
- E02：其他相关背景，学习 2 年；
- E03：其他相关背景，未报告书法学习或教学经验。

因此论文使用：

```text
blinded human raters
human structural validation
```

不把三人统一称为“三位书法专家”。

## 17.3 正式统计

Correlation 和 ICC 只使用 150 个 canonical 非重复题。隐藏重复题只用于评价者
内部稳定性。

| Score | Spearman rho | 字符聚类 bootstrap 95% CI |
|---|---:|---:|
| Production score | 0.297 | [0.148, 0.441] |
| Coverage-aware audit | 0.429 | [0.313, 0.535] |

Coverage-aware 相对 production 的相关性差：

```text
0.132
95% CI [0.062, 0.197]
```

评价者间一致性：

| 指标 | 结果 |
|---|---:|
| ICC(2,1) | 0.448 |
| ICC(2,k) | 0.709 |

隐藏重复题 pooled：

| 指标 | 结果 |
|---|---:|
| 完全一致 | 48.9% |
| 相差不超过 1 分 | 93.3% |
| Mean absolute difference | 0.578 |
| Quadratic weighted kappa | 0.634 |

结论：

- production score 与人类结构判断存在正相关；
- 相关强度不是很高，不能称为已经校准的评分；
- coverage-aware 与人工均分更一致；
- 三人均分可靠性高于单个评价者；
- 评价任务存在明显主观性；
- 结果支持“结构相似性”，不支持“审美质量”。

正式输出：

```text
artifacts/paper_ijdar/expert_validation/human_ratings_v1/paper_statistics/
```

包括：

- `human_validation_report.json`；
- `HUMAN_VALIDATION_REPORT.md`；
- `canonical_pair_ratings.csv`；
- `per_evaluator_summary.csv`；
- `per_character_summary.csv`；
- `repeat_consistency.csv`；
- `pair_disagreement_cases.csv`；
- LaTeX 表格；
- PNG/PDF 图。

人工验证结果已经写入论文，不再是占位符。

---

## 18. 论文当前状态

已写入正文的真实实验：

- Controlled Perturbation；
- Alignment Ablation；
- Structure Score Audit；
- Cross-reference；
- Feedback Failure Analysis；
- Human Structural Validation。

尚未完成的占位符：

```text
[TASK1_MAIN_BENCHMARK]
[CHARACTER_DISJOINT]
[SMARTPHONE]
```

其中：

### Task 1 Main Benchmark

当前代码与配置已经准备完成：

- 正式 ResNet-50 DeepLabV3+ 六通道实现；
- U-Net/DeepLabV3+/SegFormer-B2 公平比较配置；
- 两套 split、三模型、三随机种子，共 18 个 run；
- validation-only threshold calibration；
- 可续跑的一键执行与汇总器。

尚待 GPU 实际交付：

- 18 个正式训练 checkpoint；
- 完整训练日志；
- validation thresholds；
- test metrics；
- 三随机种子均值和样本标准差。

统一数据口径：

```text
840 complete GT files
769 QC-clean unique observations
standard split after QC: 530/119/120
character-disjoint after QC: 539/114/116
```

旧 `0.9610` B2 没有发现 exact train→test duplicate leakage，但训练中包含
mismatch 和重复加权，因此仅保留为 preliminary engineering result。

### Character-disjoint

- 原字符分配、QC-clean 派生 split、配置、launcher 和结果汇总管线均已完成；
- B2、U-Net、DeepLabV3+ 均已预注册 3 个 seed；
- 不再存在 `BLOCKED_BY_TASK1` 占位配置；
- 等 GPU smoke test 通过后运行18组正式矩阵；
- 当前不得把“代码就绪”写成“正式结果完成”。

### Smartphone / unseen-writer

- 协议和模板已完成；
- 尚未采集真实数据；
- 不能用模拟图片代替正式结果。

论文主文件：

```text
paper/manuscript.tex
```

当前无法完整编译的主要原因：

- 仓库缺少 Springer 官方 `sn-jnl.cls`；
- 仍存在三类实验占位符；
- 作者单位、邮箱、基金、伦理说明等投稿字段尚需填写。

---

## 19. 测试与质量保障

截至 2026 年 8 月 13 日，最近一次完整测试：

```text
104 passed, 2 skipped
```

同时完成：

- `compileall`；
- Ruff 检查；
- `git diff --check`；
- 人工验证统计输出完整性检查；
- 两张论文图人工查看；
- 840 GT 全量数组校验；
- reference cache schema 和 checkpoint hash 校验。

测试目录：

```text
tests/
```

已覆盖数据、训练、推理、参考库、评分、HTTP、受控扰动、对齐、反馈、数据恢复、
character-disjoint 和人工统计等模块。

---

## 20. Git 和制品状态

当前 GitHub 主分支已包含的重要提交：

```text
6d4d072  Record verified U-Net rebaseline
58abd75  Track U-Net baseline checkpoint with LFS
d560a68  Fix boundary loss under AMP
2060435  Deliver frozen SegFormer-B2 v1 model
2abf44b  Import Calli-Tongji style reference library
c3e2dde  Add B2 reference cache and structure scoring
9bab0ca  Deliver course practice scoring and feedback
ffa8ca4  Add authenticated course practice HTTP API
39e9ad8  Add controlled perturbation benchmark
2604485  Add structure-score audit
```

当前本地 `HEAD` 与 `origin/main` 位于：

```text
2604485
```

但 8 月的以下研究工作目前仍有大量本地未提交内容：

- 840 GT 数据恢复工具和报告；
- Character-disjoint 管线；
- Alignment Ablation；
- Cross-reference；
- Feedback Failure Taxonomy；
- 人工验证构造、冻结、统计；
- IJDAR 论文骨架和表格；
- 本项目总整理文档。

因此在继续多人协作前，应先：

1. 审核 `git status`；
2. 排除数据、密钥和授权图片；
3. 将代码、配置、论文和轻量报告分批 commit；
4. 大模型 checkpoint 继续使用 Git LFS；
5. `artifacts/` 中需长期保存但被忽略的正式结果，应做独立归档或受控制品发布。

---

## 21. 安全和数据治理

项目开发过程中曾在聊天中暴露过服务器密码或 API Key。本文档不记录任何密钥。

必须执行：

- 撤销并重新生成暴露过的 LLM API Key；
- 修改暴露过的 AutoDL/SSH 密码；
- 优先配置 SSH 公钥；
- 模型服务 API Key 使用随机长密钥；
- 密钥只放服务器环境变量；
- 不写入 Git、前端代码、截图、日志或 Markdown；
- Java 后端通过服务间鉴权访问模型；
- 浏览器不直连 GPU 服务。

人工评分和后续手机数据：

- 只保存匿名 evaluator/writer ID；
- 不收集不必要的姓名、学号、手机号；
- 保留 consent 和学校伦理/豁免确认；
- 明确图片保存周期和删除方式。

---

## 22. 当前已完成/未完成总清单

### P0 已完成

- [x] 独立模型工程；
- [x] 六通道 schema；
- [x] 数据审计；
- [x] 54 个异常样本确认并排除；
- [x] 840 个原始 GT 找回；
- [x] 840 个 GT 全量校验；
- [x] U-Net 可信基线；
- [x] SegFormer B0/B1/B2；
- [x] AMP Boundary Loss 修复；
- [x] 冻结 B2 checkpoint、阈值、schema 和模型卡；
- [x] 关键点容忍诊断；
- [x] 两个 100 字课程包；
- [x] 200 参考 mask cache；
- [x] 结构评分与受限对齐；
- [x] 规则反馈；
- [x] 可选 LLM 调用层；
- [x] HTTP API；
- [x] 与开发侧真实联调；
- [x] Controlled Perturbation；
- [x] Alignment Ablation；
- [x] Structure Score Audit；
- [x] Cross-reference；
- [x] Feedback Failure Taxonomy；
- [x] 150 pair 人工结构验证；
- [x] IJDAR 论文骨架和已有结果写入。

### P0/P1 待完成

- [ ] 接收并审核 Task 1 正式主分割比较；
- [ ] 运行 Character-disjoint 正式训练和评测；
- [ ] 采集真实 smartphone/unseen-writer 数据；
- [ ] 完成真实手机场景评测；
- [ ] 将 8 月本地研究代码和论文安全提交 GitHub；
- [ ] 获取 Springer `sn-jnl.cls` 并编译检查论文；
- [ ] 补齐作者、单位、伦理、基金和数据可用性声明；
- [ ] 对模型服务做长期部署，而非依赖临时 AutoDL 地址；
- [ ] 对外部 LLM 的真实返回和降级路径做一次正式验收。

### P2 可做但不阻塞近期论文

- [ ] 冻结完整困难集并跑 U-Net/B2 对照；
- [ ] 扩充 same-style different-instance 参考对；
- [ ] 建立 coverage-aware v2 的预注册验证；
- [ ] 补充书法专业评价者；
- [ ] 扩充真实课程或具体碑帖；
- [ ] OCR 支持任意图片输入；
- [ ] 更细的笔画实例而非方向连通区。

### 目前不做

- [ ] SAM2 大规模训练；
- [ ] 新分割架构搜索；
- [ ] 为漂亮结果继续调 alignment；
- [ ] 根据人工评分事后修改 v1 production formula；
- [ ] LLM faithfulness 大实验；
- [ ] 端侧蒸馏、ONNX 和 INT8；
- [ ] 通用任意字体审美评分。

---

## 23. 接下来最合理的推进顺序

### 第一步：保存当前成果

1. 备份旧数据归档和恢复后的 GT；
2. 整理本地未提交文件；
3. 分批 commit/push 研究代码、论文和文档；
4. 不把授权图片、cache、密钥和原始个人信息提交 Git。

### 第二步：并行等待 Task 1

Task 1 由其他成员完成期间，本项目负责人继续：

- 准备手机真实采集；
- 确定匿名 writer ID；
- 确认 consent/伦理要求；
- 先收 20–30 张 pilot 检查输入流程；
- 再扩充到约 100–200 张正式图片。

### 第三步：Task 1 到达后立即审核

检查：

- 数据是否为 769 条固定 QC-clean 数据，而不是直接使用 840；
- exclusion、manifest 和 split SHA-256 是否正确；
- standard split 是否为 530/119/120；
- character-disjoint 是否为 539/114/116；
- 原字符分配 SHA 是否仍为
  `eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e`；
- threshold 是否只用 validation；
- test 是否只评一次；
- seed 是否按计划；
- DeepLabV3+ 是否真正实现；
- 是否保留负面结果；
- 是否有 checkpoint、日志和 run manifest。

### 第四步：执行 Character-disjoint

在 Task 1 baseline 就绪后：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.run_character_disjoint_benchmark --execute
```

执行前再次核对 split SHA-256，禁止改划分。

### 第五步：论文收尾

- 填 Task 1 表格；
- 填 Character-disjoint；
- 填 Smartphone；
- 编译 PDF；
- 做引用、图表、字数和伦理声明检查；
- 再决定是否投稿 IJDAR。

---

## 24. 常用复现命令

## 24.1 安装

```powershell
git clone https://github.com/LiuXiaofan-0321/OneStroke2026.git
cd OneStroke2026
git lfs install
git lfs pull

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[train,serve,paper,dev]"
```

## 24.2 验证 B2 推理

```powershell
python infer.py `
  --config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --image ".\demo.png" `
  --output-dir ".\artifacts\demo_b2" `
  --model-version "segformer-b2-v1"
```

## 24.3 构建课程 catalog

```powershell
$env:PYTHONPATH = "$PWD\src"

python -m onestroke_model.scripts.build_course_catalog `
  --course-config ".\configs\course_packs.yaml" `
  --output ".\artifacts\course_packs\catalog.json" `
  --require-cache
```

## 24.4 单次课程分析

```powershell
python -m onestroke_model.scripts.analyze_course_practice `
  --image ".\user_character.png" `
  --course-id "ouyang_xun_regular_100_beta" `
  --target-char "亮" `
  --model-config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --course-config ".\configs\course_packs.yaml" `
  --output-dir ".\artifacts\practice\example"
```

## 24.5 本地启动 HTTP 服务

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:ONESTROKE_API_KEY = "<server-side-random-secret>"
$env:ONESTROKE_CHECKPOINT = "$PWD\checkpoints\segformer_b2_v1\best.pt"
$env:ONESTROKE_ARTIFACT_ROOT = "$PWD\artifacts\http_api\practice"

python -m onestroke_model.scripts.serve_http_api `
  --host 0.0.0.0 `
  --port 6008
```

## 24.6 重新生成人工验证统计

```powershell
$env:PYTHONPATH = "$PWD\src"

python -m onestroke_model.scripts.build_human_validation_statistics `
  --pairs ".\artifacts\paper_ijdar\expert_validation\frozen_study_v1\internal_DO_NOT_SEND_TO_EVALUATORS\expert_rating_pairs.csv" `
  --ratings ".\artifacts\paper_ijdar\expert_validation\human_ratings_v1\merged_ratings.csv" `
  --raw-returns-dir ".\artifacts\paper_ijdar\expert_validation\human_ratings_v1\raw_returns" `
  --output-dir ".\artifacts\paper_ijdar\expert_validation\human_ratings_v1\paper_statistics" `
  --bootstrap-iterations 10000 `
  --seed 20260812
```

## 24.7 测试

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m compileall -q src tests
python -m pytest -q
python -m ruff check src tests
git diff --check
```

---

## 25. 关键文件索引

### 模型

```text
checkpoints/segformer_b2_v1/best.pt
configs/segformer_b2_v1_delivery.yaml
docs/model_card_segformer_b2_v1.md
releases/segformer_b2_v1/
```

### 数据

```text
DATA_RECOVERY_REPORT.md
data/legacy_gt_v1/output_img/
artifacts/data_audit/
artifacts/data_recovery/
```

### 课程和参考

```text
configs/course_packs.yaml
configs/style_registry.yaml
references/calli_tongji_beta_manifest.csv
references/cache/segformer_b2_v1/index.json
docs/course_practice_model_handoff.md
```

### HTTP

```text
src/onestroke_model/http_api.py
src/onestroke_model/scripts/serve_http_api.py
docs/http_api_handoff.md
```

### 论文

```text
paper/manuscript.tex
paper/sections/
paper/tables/
paper/supplementary/PROVENANCE.md
artifacts/paper_ijdar/
```

### 人工验证

```text
artifacts/paper_ijdar/expert_validation/frozen_study_v1/
artifacts/paper_ijdar/expert_validation/human_ratings_v1/
src/onestroke_model/human_validation_statistics.py
```

---

## 26. 对外汇报时建议使用的简版结论

> 项目已经完成从原始六通道数据恢复、可信 U-Net 基线、SegFormer-B2 高精度
> 分割，到课程参考字条件化评分、结构化建议和 HTTP 软件联调的完整闭环。
> 冻结 B2 在五方向分割上达到 0.961 Macro Dice，相比 U-Net 提升约 6.97 个
> 百分点。项目还在 200 个真实参考上完成了受控扰动、对齐消融、评分审计和
> 反馈失败分析，并使用 150 个自然同字不同实例 pair、3 位盲评者完成了人工
> 结构验证。Production score 与人工均分的 Spearman 相关为 0.297，
> coverage-aware audit 为 0.429。当前系统能够提供可解释的参考结构匹配，
> 但不将其宣传为通用书法审美分。论文剩余的核心工作是 Task 1 正式多模型
> 比较、character-disjoint 泛化和真实手机/未见书写者验证。
