# “一笔成章”模型模块完整训练路线：SAM2 + SegFormer-B2 + 字体风格选择 + 云端/端侧双模型

更新时间：2026-07-09  
适用范围：“一笔成章”模型模块 7–8 月研发  
当前新增需求：软件端加入字体/书家风格选择功能，例如“赵孟頫楷体”。模型侧需要支持用户选择目标风格后，给出更符合该风格的分割、评价和反馈。

## 1. 结论先行

新的模型路线不是简单地“再训练一个模型”，而是升级成四层体系：

```text
通用分割主线：SegFormer-B2
    ↓
SAM2 辅助教师：边界修正、伪标签、困难样本分析、参考字分割
    ↓
字体/书家风格评价模块：根据 target_style_id 或参考字图输出风格化反馈
    ↓
云端/端侧双模型：云端高精度教师，端侧轻量学生
```

核心判断：

1. 7 月仍以 SegFormer-B2 六通道分割为主体，先把“看懂字”的能力做稳。
2. SAM2 不直接作为最终唯一模型，而是作为辅助教师、边界修正器和参考字标注工具。
3. 字体选择功能不应该导致“每个字体训练一个完整模型”，而应该做成“通用结构模型 + 风格条件模块”。
4. 后续产品形态应采用云端/端侧双模型：
   - 云端模型负责高精度分割、复杂风格评价、训练教师和异步精修。
   - 端侧模型负责低延迟基础分割和基础反馈。
5. 7 月交付云端高精度主体，8 月开始端侧蒸馏和风格条件化。

## 2. 为什么仍然保留 SegFormer-B2 作为主线

SegFormer-B2 适合承担本项目 7 月主线，原因有三点。

第一，它是语义分割模型，而我们的核心输出就是六通道概率图：

- `vec1`
- `vec2`
- `vec3`
- `vec4`
- `vec5`
- `keypoint`

第二，它是 prompt-free 模型。用户上传一张字图后，不需要人工点选、不需要框选，模型可以直接输出完整汉字的六通道分割。这非常符合软件端自动反馈流程。

第三，SegFormer 的结构天然适合汉字：

- 多尺度特征适合捕捉整体字形结构。
- Transformer 编码器适合处理远距离笔画关系。
- 轻量 MLP 解码器工程复杂度不高，便于快速落地。

所以，7 月主体模型定义为：

> SegFormer-B2 六通道多标签分割模型。

它不是普通语义分割的 Softmax 多类分类，而是六个独立 Sigmoid 通道。原因是笔画交叉区域允许多个通道重叠，不能用互斥 Softmax。

## 3. SAM2 在项目中的正确位置

SAM2 很强，但它和我们的任务并不是天然完全一致。

SAM2 的原始定位是 promptable segmentation，即通过点、框、mask 等提示得到目标区域。我们的软件端第一需求是自动输入整张汉字图，直接输出六通道结构图。这个差异决定了：

> SAM2 不适合作为 7 月唯一在线主模型，但非常适合作为训练辅助、边界教师和数据增强工具。

### 3.1 SAM2 不直接作为唯一主模型的原因

1. 当前数据量偏小，直接完整微调 SAM2 风险大。
2. SAM2 需要 prompt，而软件端希望自动分析整字。
3. 我们的输出是六通道多标签结构，不是单个实例 mask。
4. 直接部署 SAM2 到端侧成本高，推理链路也更复杂。
5. 官方训练示例偏重较大算力环境，不适合把全部 7 月计划押在完整微调上。

### 3.2 SAM2 应该承担的四个角色

#### 角色 A：笔画实例级教师

旧数据里不仅有六通道标签，还能从单笔画 mask 中构造“笔画实例样本”。

对于每一笔，可以生成：

- 单笔画 mask
- bounding box prompt
- positive point
- negative points
- 对应通道类别：`vec1–vec5`
- 所属字符
- 所属样本
- 所属风格，后续扩展

这样原本 894 个整字样本，可以转成几千个笔画实例样本。对 SAM2 来说，这比只看 894 张整字更合理。

#### 角色 B：边界修正器

汉字分割最难的地方通常不是大片区域，而是：

- 交叉
- 粘连
- 端点
- 起收笔
- 笔画边界

SAM2 可以在这些区域上提供更精细的实例边界。我们不一定把它的输出直接当真值，而是用于：

- 生成边界监督
- 修正明显粗糙的标签边缘
- 对 SegFormer 输出做离线对比
- 找出高不确定区域

#### 角色 C：伪标签和困难样本挖掘工具

当新增样本没有完整六通道标注时，可以用 SAM2 辅助生成候选 mask，再由人工抽检。

流程：

```text
新增字图
    ↓
SAM2 根据自动 prompt 生成候选笔画 mask
    ↓
规则或轻量分类器分配 vec1–vec5
    ↓
人工检查 20%–30%
    ↓
加入训练集或困难集
```

#### 角色 D：风格参考字标注工具

字体选择功能需要“目标参考字”。例如用户选择赵孟頫楷体，系统需要知道目标字长什么样。

SAM2 可以帮助处理参考库：

- 给标准字图自动分割笔画区域。
- 生成参考字骨架。
- 提取交叉点、端点、外轮廓。
- 帮助建立“目标风格结构特征”。

这对 8 月风格评价非常重要。

## 4. 云端/端侧双模型是否还需要

需要，而且新增字体选择功能后更需要。

原因是：字体风格评价比普通分割更重。端侧要做低延迟，云端要做高精度和复杂分析，两者职责不同。

### 4.1 云端模型定位

云端模型是高精度教师和完整反馈模型。

建议云端包含：

```text
Cloud Teacher Model
├── SegFormer-B2 六通道分割主干
├── SAM2 辅助边界/实例教师
├── 字体风格参考库
├── 风格条件评价模块
└── 复杂诊断与可视化输出
```

云端负责：

- 高精度六通道分割
- 困难字、粘连、交叉区域精修
- 风格化评价
- 生成训练伪标签
- 给端侧学生模型蒸馏
- 保存实验结果和失败案例

### 4.2 端侧模型定位

端侧模型是轻量学生，用于实时或弱网场景。

建议端侧候选：

- SegFormer-B0 student
- MobileNetV3 + DeepLab/轻量 FPN
- MobileSAM 只作为对照或辅助，不作为第一端侧主线

端侧负责：

- 快速六通道基础分割
- 粗略关键点检测
- 基础结构反馈
- 离线/弱网时给即时结果

端侧不建议一开始承载完整风格评价。第一版可以只输出基础结构结果，风格评价由云端异步返回。

### 4.3 产品调用方式

推荐软件端采用“双阶段反馈”：

```text
用户写完 / 上传
    ↓
端侧轻量模型快速返回基础分割和初步反馈
    ↓
云端高精度模型异步复核
    ↓
如果云端结果更可靠，则刷新详细反馈和风格化建议
```

这样体验上不会卡住，模型上也能保留高精度空间。

## 5. 总体模型架构

### 5.1 7 月云端主体：SegFormer-B2 六通道分割

输入：

```text
RGB 汉字图像
原始尺寸
```

预处理：

```text
等比例填充缩放到 512×512
归一化
保留原始尺寸和 padding 信息
```

输出：

```text
[H, W, 6] probability map
六张 binary masks
每通道阈值
推理耗时
```

通道顺序固定：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

模型结构：

```text
Image
  ↓
SegFormer-B2 encoder
  ↓
MLP decoder
  ↓
6-channel sigmoid logits
  ↓
probability maps + masks
```

注意：

- 禁止 Softmax。
- 每个通道独立 Sigmoid。
- 交叉区域允许多个方向通道同时为 1。
- keypoint 是独立稀疏通道，损失权重要单独处理。

### 5.2 SAM2 辅助分支

SAM2 分支不直接替代 SegFormer-B2，而是训练与数据层的辅助系统。

结构：

```text
单笔画实例图 / 整字图
    ↓
自动生成 box / point prompt
    ↓
SAM2 image encoder
    ↓
SAM2 mask decoder
    ↓
单笔画 mask / 边界 / 不确定区域
```

训练策略：

1. 冻结 SAM2 大部分参数。
2. 先只训练轻量输出头或 adapter。
3. 如果效果明显，再尝试末端 LoRA。
4. 不做全量微调，除非后续数据量和算力都上来。

SAM2 输出用途：

- 形成 boundary target。
- 修正训练标签边缘。
- 作为 SegFormer 的蒸馏教师之一。
- 为参考字图生成结构特征。
- 统计困难样本。

### 5.3 8 月风格条件模块

字体选择功能的模型接口不能只输入图片，还需要输入目标风格。

风格条件模块输入：

```text
SegFormer 分割特征
六通道 mask
char_id
target_style_id
reference_image 或 reference_id
```

输出：

```text
global_style_score
structure_score
stroke_shape_score
keypoint_position_score
stroke_feedback
visual_diff_map
```

推荐分两版实现。

#### 版本 A：Style ID Embedding

```text
target_style_id
    ↓
style embedding
    ↓
与 SegFormer 特征融合
    ↓
风格评分 / 偏差类别
```

优点：

- 实现快。
- 适合少量固定风格。
- 适合第一版产品演示。

缺点：

- 新增风格需要微调。
- 对未见风格泛化弱。

#### 版本 B：Reference Encoder

```text
学生字图
目标参考字图
    ↓
共享或双塔 encoder
    ↓
结构对齐
    ↓
差异特征
    ↓
风格反馈
```

优点：

- 更符合“选择字帖/字体”的产品逻辑。
- 新增风格时只要有参考图，扩展性更好。
- 便于做可视化差异图。

缺点：

- 对齐问题更难。
- 数据要求更高。
- 训练复杂度更高。

建议：

> 8 月先做 Style ID Embedding + 几何规则 baseline；Reference Encoder 作为 9 月扩展方向。

## 6. 数据体系设计

新增字体选择后，数据不再只有“图片 + 六通道标签”，而是要分成三类。

### 6.1 数据 A：通用六通道分割数据

这是 7 月主线。

每条样本包含：

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 样本 ID |
| `char_id` | 汉字 ID |
| `writer_id` | 书写者 ID |
| `source_id` | 来源 ID |
| `image_path` | RGB 图像 |
| `vec1_path` | 通道 1 标签 |
| `vec2_path` | 通道 2 标签 |
| `vec3_path` | 通道 3 标签 |
| `vec4_path` | 通道 4 标签 |
| `vec5_path` | 通道 5 标签 |
| `keypoint_path` | 关键点标签 |
| `split` | train/val/test |

当前已完成的地基：

- 审计旧数据
- 生成 `manifest.csv`
- 生成固定 `splits.csv`
- 固定六通道 schema

### 6.2 数据 B：SAM2 笔画实例数据

从旧数据的单笔画 mask 派生。

每条样本包含：

| 字段 | 含义 |
| --- | --- |
| `instance_id` | 笔画实例 ID |
| `sample_id` | 所属整字样本 |
| `char_id` | 汉字 ID |
| `channel` | `vec1–vec5` |
| `stroke_mask_path` | 单笔画 mask |
| `box_prompt` | 外接框 prompt |
| `positive_points` | 笔画内部点 |
| `negative_points` | 背景/其他笔画点 |
| `difficulty_tags` | 交叉、粘连、端点等 |

用途：

- SAM2 受控实验
- 单笔画边界教师
- 交叉区域分析
- 伪标签生成

### 6.3 数据 C：字体/书家风格数据

这是新增字体选择功能需要的数据。

每条样本包含：

| 字段 | 含义 |
| --- | --- |
| `style_id` | 风格 ID，例如 `zhao_mengfu_kaishu` |
| `style_display_name` | 前端显示名，例如“赵孟頫楷体” |
| `script_type` | 楷书、行书、隶书等 |
| `reference_id` | 参考字 ID |
| `reference_image_path` | 目标参考字图 |
| `char_id` | 对应汉字 |
| `source_book` | 来源字帖/碑帖 |
| `license_note` | 版权或来源说明 |
| `quality_status` | 是否人工确认 |

命名建议：

```text
zhao_mengfu_kaishu
ouyang_xun_kaishu
yan_zhenqing_kaishu
liu_gongquan_kaishu
```

前端可以显示中文名，但模型接口必须使用稳定 ID。

## 7. 训练路线详解

### 阶段 0：工程与数据地基

时间：已开始，7 月 9 日前后完成主体。

目标：

- 建立独立模型工程。
- 数据审计。
- 固定划分。
- 固定六通道 schema。
- 准备训练/评测/推理入口。

当前工程已有：

- `train.py`
- `eval.py`
- `infer.py`
- U-Net baseline
- SegFormer-B2 wrapper
- 六通道损失函数
- 基础指标
- manifest/split 生成脚本

### 阶段 1：U-Net 重测基线

时间：7 月 10–13 日。

目的不是追求 U-Net 最强，而是建立可信 baseline。

训练设置：

- 输入尺寸：512×512
- 输出：六通道 logits
- 激活：Sigmoid
- 损失：BCE + Dice
- 优化器：AdamW
- 固定 train/val/test split

评测指标：

- 五方向 Macro Dice
- 五方向 Macro IoU
- 每通道 Precision/Recall
- keypoint F1
- Boundary F1
- 按字符统计失败案例
- 按困难类型统计失败案例

产出：

- `unet_rebaseline/best.pt`
- `metrics.json`
- 预测对比图
- 失败案例清单

### 阶段 2：SegFormer-B2 主线训练

时间：7 月 14–20 日。

这是 7 月最重要的一步。

训练输入：

```text
RGB image, 512×512
```

训练输出：

```text
6-channel logits
```

损失函数：

```text
direction_loss = weighted_BCE(vec1–vec5) + Dice(vec1–vec5)
keypoint_loss  = Focal(keypoint) + Dice(keypoint)
boundary_loss  = BCE/Dice(boundary)
total_loss     = direction_loss + keypoint_loss + 0.2 * boundary_loss
```

训练策略：

- ImageNet/通用预训练权重初始化。
- 编码器小学习率。
- 解码器大学习率。
- AdamW。
- 混合精度。
- Cosine schedule。
- Early stopping。
- 最终候选跑 3 个随机种子。

实验顺序：

1. 基础 BCE + Dice。
2. 加 keypoint Focal。
3. 加 boundary loss。
4. 加困难样本重采样。
5. 加 SAM2 边界教师。

产出：

- 第一版云端高精度 SegFormer-B2。
- 与 U-Net 重测基线的定量对比。
- 困难集对比图。

### 阶段 3：SAM2 受控实验

时间：7 月 21–25 日。

目标不是“押宝 SAM2”，而是验证 SAM2 是否能给本项目提供增益。

实验数据：

- 从旧数据构造笔画实例数据。
- 每个笔画生成 box prompt 和 point prompt。
- 与整字六通道 split 保持一致，避免泄漏。

实验路线：

```text
SAM2 zero-shot prompt
    ↓
冻结 encoder，只训练轻量头/adapter
    ↓
末端 LoRA
    ↓
输出单笔画 mask / boundary
    ↓
用于 SegFormer 蒸馏或边界监督
```

评测指标：

- 单笔画 Dice
- 单笔画 Boundary F1
- 交叉区域 Boundary F1
- 端点区域 Recall
- 对 SegFormer 训练后的增益

止损条件：

- 如果 SAM2 在 7 月 25 日前不能明显提升交叉/端点 Boundary F1，就不继续扩大实验。
- 如果 SAM2 只在少数样本上好看，但无法稳定提升 SegFormer，则作为研究记录和标注辅助工具。
- 不做全量 SAM2 微调，除非后续数据量、算力和时间都满足。

### 阶段 4：云端教师模型定型

时间：7 月 26–31 日。

云端教师模型不是单一模型文件，而是一套高精度推理和训练资产。

组成：

```text
SegFormer-B2 best checkpoint
SAM2-assisted boundary refinement records
channel thresholds
style schema placeholder
data version
metrics report
failure cases
```

定型内容：

- 三随机种子训练。
- 报告均值和标准差。
- 固定最佳 checkpoint。
- 固定推理阈值。
- 固定数据版本。
- 生成 30 个代表性结果供书法成员复核。

月底验收：

- Macro Dice 相比 U-Net 提升至少 3 个百分点。
- keypoint F1 提升至少 5 个百分点。
- 困难集 Macro Dice 提升至少 5 个百分点。
- 任一主要方向通道不能明显下降。
- 单图推理可以一条命令运行。

### 阶段 5：字体/风格参考库

时间：8 月上旬。

新增字体选择功能必须先解决“目标标准”。

第一版不要一口气支持太多风格。建议先做：

1. 赵孟頫楷体
2. 欧阳询楷体
3. 颜真卿楷体

如果时间紧，先只做赵孟頫楷体，把链路跑通。

需要建立：

```text
style_registry.yaml
reference_manifest.csv
reference_images/
reference_masks/
reference_features/
```

每个参考字需要：

- 标准字图
- 字符 ID
- 风格 ID
- 来源说明
- 质量状态
- 可选六通道 mask
- 可选骨架/关键点

SAM2 在这一阶段用于帮助参考字分割，但最终高价值参考必须人工抽检。

### 阶段 6：风格几何 baseline

时间：8 月中旬。

在训练复杂神经网络前，先做可解释 baseline。

基于 SegFormer 输出和参考字图，计算：

- 字形宽高比
- 外接框位置
- 字形重心
- 笔画角度
- 笔画长度
- 笔画粗细
- 起笔/收笔位置
- 关键点偏移
- 交叉点偏移
- 骨架距离
- 轮廓距离

输出示例：

```json
{
  "structure_score": 0.78,
  "stroke_shape_score": 0.83,
  "keypoint_position_score": 0.76,
  "problems": [
    {
      "type": "center_shift",
      "message": "整体重心偏右"
    },
    {
      "type": "stroke_angle",
      "message": "主横倾斜角度与赵孟頫楷体参考差异较大"
    }
  ]
}
```

这一步很重要，因为它：

- 数据需求小。
- 可解释。
- 容易给前端展示。
- 能作为风格神经模型的 baseline。

### 阶段 7：风格条件化模型

时间：8 月下旬开始。

第一版推荐做 Style ID Embedding。

模型：

```text
Image
  ↓
SegFormer-B2 encoder / frozen or partially frozen
  ↓
segmentation feature
  ↓                 target_style_id
mask feature    +   style embedding
  ↓
style head
  ↓
style scores + feedback tags
```

训练任务：

```text
Task 1: 六通道分割
Task 2: 风格评分回归/分类
Task 3: 偏差类型分类
Task 4: 与参考字的对比学习
```

人工标签建议先用三级：

```text
0 = 明显不符合目标风格
1 = 部分符合，但有明显问题
2 = 基本符合目标风格
```

不要一开始做 100 分制。书法评价主观性强，细分分数的噪声会很大。

## 8. 端侧学生模型训练路线

端侧模型放在 8 月，不抢 7 月主线。

### 8.1 为什么端侧需要蒸馏

SegFormer-B2 和 SAM2 都偏重，端侧直接部署成本高。

端侧目标：

- 快速
- 稳定
- 模型小
- 能离线跑基础反馈
- 与云端结果保持一致

所以端侧不从零训练，而是从云端教师蒸馏。

### 8.2 学生模型候选

优先顺序：

1. SegFormer-B0 student
2. MobileNetV3 + 轻量 FPN
3. MobileSAM 作为对照，不作为第一主线

选择标准：

- 模型大小
- CPU/移动端推理耗时
- ONNX 导出难度
- 量化后精度损失
- 对六通道分割的稳定性

### 8.3 蒸馏目标

教师：

```text
SegFormer-B2 cloud teacher
SAM2 boundary teacher
人工标签
```

学生学习：

```text
hard label loss: 学人工六通道标签
soft logit loss: 学 SegFormer-B2 probability map
boundary distill: 学 SAM2/教师边界
feature distill: 学中间特征，可选
```

损失：

```text
student_total_loss =
  hard_label_loss
  + 0.5 * soft_probability_distill
  + 0.2 * boundary_distill
  + optional_feature_distill
```

### 8.4 量化与部署

端侧路线：

```text
PyTorch checkpoint
    ↓
ONNX export
    ↓
ONNX Runtime / NCNN / TFLite 评估
    ↓
INT8 QAT 或 PTQ
    ↓
Flutter / App 调用
```

验收指标：

- 模型大小，例如小于 20–40 MB，具体看设备。
- 单图推理延迟满足产品要求。
- Macro Dice 相比云端教师下降不超过可接受阈值。
- keypoint F1 不出现灾难性下降。
- 输出 schema 与云端一致。

## 9. 接口设计

### 9.1 Schema v1：7 月分割接口

输入：

```json
{
  "image": "RGB image",
  "original_size": [H, W]
}
```

输出：

```json
{
  "schema_version": 1,
  "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
  "probability_map": "[H,W,6]",
  "binary_masks": "[H,W,6]",
  "thresholds": {
    "vec1": 0.5,
    "vec2": 0.5,
    "vec3": 0.5,
    "vec4": 0.5,
    "vec5": 0.5,
    "keypoint": 0.45
  },
  "latency_ms": 0
}
```

### 9.2 Schema v2：字体选择接口

输入：

```json
{
  "image": "RGB image",
  "original_size": [H, W],
  "char_id": "yong",
  "target_style_id": "zhao_mengfu_kaishu",
  "reference_id": "zhao_mengfu_kaishu_yong_v1"
}
```

输出：

```json
{
  "schema_version": 2,
  "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
  "probability_map": "[H,W,6]",
  "binary_masks": "[H,W,6]",
  "target_style_id": "zhao_mengfu_kaishu",
  "style_scores": {
    "global": 0.82,
    "structure": 0.78,
    "stroke_shape": 0.85,
    "keypoint_position": 0.80
  },
  "feedback": [
    {
      "type": "structure",
      "severity": "medium",
      "message": "整体重心略偏右，与目标风格参考存在差异"
    }
  ],
  "latency_ms": 0
}
```

### 9.3 云端与端侧输出一致性

云端和端侧都必须使用同一套通道顺序：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

差别只在能力等级：

| 能力 | 端侧 | 云端 |
| --- | --- | --- |
| 六通道基础分割 | 支持 | 支持 |
| 关键点检测 | 支持 | 支持，更准 |
| 困难区域精修 | 有限 | 支持 |
| 字体风格评价 | 第一版可不支持或只支持简化版 | 支持 |
| 可视化差异图 | 可选 | 支持 |
| 训练伪标签生成 | 不支持 | 支持 |

## 10. 评测体系

### 10.1 分割评测

用于 U-Net、SegFormer-B2、端侧学生模型。

指标：

- 五方向 Macro Dice
- 五方向 Macro IoU
- 每通道 Precision
- 每通道 Recall
- keypoint F1
- Boundary F1
- 困难集 Macro Dice
- 按字符统计
- 按困难类型统计

### 10.2 SAM2 辅助评测

SAM2 不只看整字最终分数，而要看它是否提供了 SegFormer 没有的价值。

指标：

- 单笔画 Dice
- 单笔画 Boundary F1
- 交叉区域提升
- 端点区域提升
- 伪标签人工通过率
- 对 SegFormer 训练后的实际增益

如果 SAM2 自己分得不错，但不能提升最终 SegFormer 或风格评价，就不继续扩大。

### 10.3 字体风格评测

字体选择功能不能只看 Dice。

指标：

- 与人工风格评分的 Spearman 相关系数
- 三级风格标签准确率
- 偏差类型分类准确率
- 同一输入选择不同风格时反馈是否合理变化
- 书法专业成员人工复核通过率

第一版验收建议：

- 每个目标风格至少 30 个代表样本人工复核。
- 不要求评分完全准确，但不能出现明显反常反馈。
- 对同一个字选择不同目标风格时，输出的参考和建议必须有区别。

### 10.4 端侧评测

指标：

- 模型大小
- CPU 推理耗时
- 移动端推理耗时
- 峰值内存
- Macro Dice 相比云端下降
- keypoint F1 相比云端下降
- ONNX/移动端输出与 PyTorch 输出误差

## 11. 7–8 月排期

### 7 月 9–13 日：U-Net 基线和数据地基收尾

- 修正数据划分。
- 跑 U-Net baseline。
- 输出正式 metrics。
- 输出失败案例。
- 开始构造 SAM2 笔画实例 manifest。

### 7 月 14–20 日：SegFormer-B2 主线

- 跑基础 SegFormer-B2。
- 加 keypoint Focal。
- 加 boundary loss。
- 加困难样本重采样。
- 冻结第一版云端候选。

### 7 月 21–25 日：SAM2 受控实验

- 构造 prompt 数据。
- 跑 zero-shot SAM2。
- 跑冻结 encoder + 轻量头/adapter。
- 如有效，再跑末端 LoRA。
- 判断是否用于 boundary teacher。

### 7 月 26–31 日：云端教师定型

- 3 seed 训练。
- 输出均值/标准差。
- 固定 checkpoint。
- 固定 thresholds。
- 输出报告和可视化。
- 30 个代表样本人工复核。

### 8 月上旬：字体参考库

- 定第一批支持风格。
- 建 `style_registry.yaml`。
- 建 `reference_manifest.csv`。
- 整理参考字图。
- 用 SAM2 辅助参考字分割。

### 8 月中旬：风格几何 baseline

- 对齐学生字和参考字。
- 提取几何差异特征。
- 输出第一版风格化反馈。
- 让书法成员复核反馈是否合理。

### 8 月下旬：端侧蒸馏与风格条件模型

- 训练 SegFormer-B0 student。
- 做 ONNX 导出。
- 做 PTQ/QAT。
- 尝试 Style ID Embedding 风格头。
- 与云端模型做一致性评测。

## 12. 风险与止损点

### 12.1 SAM2 风险

风险：

- 数据太小。
- prompt 构造不稳定。
- 微调成本高。
- 与六通道任务不完全一致。

止损：

- 7 月 25 日前不能提升 Boundary F1，就停止扩展。
- 不做全量微调。
- 保留为辅助标注和研究记录。

### 12.2 字体风格风险

风险：

- 参考字来源不统一。
- 风格标签主观。
- 不同书家同一字差异复杂。
- 前端可能把“字体文件”和“书家风格”混用。

止损：

- 第一版只支持 1–3 种风格。
- 先做几何 baseline，不急着训练复杂风格网络。
- 所有风格使用稳定 `style_id`。
- 人工评分先用三级，不用百分制。

### 12.3 端侧部署风险

风险：

- keypoint 稀疏通道量化后下降明显。
- ONNX 导出和移动端算子支持不完整。
- 端侧模型太小导致交叉区域性能下降。

止损：

- 端侧第一版只保证基础分割。
- 风格评价先云端完成。
- 若 SegFormer-B0 端侧效果不好，切换 MobileNetV3 + FPN。

## 13. 团队分工建议

### 刘小凡

- 模型路线总负责。
- SegFormer-B2 主线。
- SAM2 受控实验。
- 云端教师定型。
- 风格条件模型设计。
- 实验报告。

### 张荣昊

- 数据审计。
- U-Net baseline。
- 批量实验脚本。
- SAM2 笔画实例数据构造。
- 指标整理。

### 高怡然

- 新增样本规范。
- 困难案例标记。
- 参考字图质量复核。
- 风格反馈人工复核。

### 前后端成员

- 确定 `target_style_id` 接口。
- 确定云端/端侧调用策略。
- 展示基础反馈与云端异步精修结果。
- 不在前端写死模型通道顺序。

## 14. 当前马上要做的事

最紧急的是不要让字体选择打乱 7 月主体。

当前优先级：

1. 跑 U-Net 重测基线。
2. 跑 SegFormer-B2 主线。
3. 构造 SAM2 笔画实例数据。
4. 建立 `style_id` 命名规范。
5. 和前端确认字体选择接口只传 `target_style_id`，不要只传中文显示名。

推荐本周额外新增两个文件：

```text
configs/style_registry.yaml
artifacts/style/reference_manifest_template.csv
```

但它们不阻塞 7 月训练。

## 15. 最终模型形态

月底可以对外描述为：

> 本项目采用 SegFormer-B2 作为云端高精度六通道书法结构分割主干，引入 SAM2 作为笔画实例边界教师和参考字辅助标注工具；后续通过云端教师向端侧轻量模型蒸馏，实现云端高精度与端侧低延迟的双模型部署。针对软件新增的字体选择功能，模型接口预留 `target_style_id` 和参考字输入，8 月开始扩展风格条件化评价模块，实现面向赵孟頫楷体等目标风格的结构化反馈。

这个表述既能体现 SAM2，也能体现 SegFormer-B2，还能解释为什么不是简单把 SAM2 端到端塞进产品里。

## 16. 参考资料

- [SAM2 官方仓库](https://github.com/facebookresearch/sam2)
- [SAM2 官方训练说明](https://github.com/facebookresearch/sam2/blob/main/training/README.md)
- [SegFormer 论文](https://arxiv.org/abs/2105.15203)
- [MobileSAM 官方仓库](https://github.com/ChaoningZhang/MobileSAM)

