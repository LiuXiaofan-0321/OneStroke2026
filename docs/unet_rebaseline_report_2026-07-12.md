# U-Net 重测基线报告（v1）

负责人：张荣昊  
整理日期：2026 年 7 月 12 日  
状态：已完成；作为 SegFormer-B2 的正式对照基线。

## 1. 数据复核结论

异常样本复核文件共 54 条，与 manifest 中的 54 条异常记录完全一一对应，无遗漏、无额外样本。

| 结论 | 数量 |
| --- | ---: |
| 完整可用样本 | 840 |
| 异常样本 | 54 |
| 可修复 | 0 |
| 剔除 | 54 |

54 条异常均为 `missing_mask`，来自 `char_id 40`、`41`、`42`，各 18 条。它们分别保存不同书写者的姓、名首字、名尾字，而不是“同一汉字的多书写者样本”；同时缺少训练需要的 mask。因此全部剔除是合理且可复现的决策。

## 2. 实际训练配置

本次基线使用 [train_unet_rebaseline_v1.yaml](../configs/train_unet_rebaseline_v1.yaml)：

- U-Net，`base_channels=32`，输入 `512×512`，六通道独立 Sigmoid 输出；
- train / val / test 为 600 / 120 / 120；
- AdamW，学习率 `3e-4`，余弦退火至 `1e-6`，最多 80 epoch，早停耐心值 12；
- 五方向：自动类别加权 BCE + Dice；关键点：Focal + Dice；边界损失权重 0.2；
- Mac Apple Silicon MPS 上训练，`num_workers=0`，在 epoch 75 早停。

checkpoint 采用 schema v1，通道顺序与当前工程一致：`vec1, vec2, vec3, vec4, vec5, keypoint`。该 checkpoint 的网络宽度为 32，**不能用 `base_channels=64` 的通用配置加载**。

## 3. 结果

| 指标 | 验证集 | 测试集 |
| --- | ---: | ---: |
| 五方向 Macro Dice | 0.8850 | **0.8913** |
| 五方向 Macro IoU | 0.7951 | **0.8049** |
| Keypoint F1 | 0.7108 | **0.7531** |
| 五方向 Boundary F1 | 0.7012 | **0.7385** |

测试集逐通道 Dice：

| 通道 | vec1 | vec2 | vec3 | vec4 | vec5 | keypoint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dice | 0.9068 | 0.9014 | 0.9136 | 0.8909 | 0.8440 | 0.7531 |

当前主要瓶颈：`keypoint` 最难（F1 0.7531，Recall 0.7298）；方向通道中 `vec5` 最弱（Dice 0.8440）。这两项应作为 SegFormer 消融和困难案例分析的重点。

## 4. 交付与复现说明

- checkpoint 约 93 MB，已用 Git LFS 同步为 `checkpoints/unet_rebaseline_v1/best.pt`。克隆后需执行 `git lfs pull` 才会得到真实权重文件。
- 原始 JSON 指标与完整异常样本复核表保留在项目共享交付目录；它们包含机器绝对路径，未直接提交到仓库。
- 当前训练、评测和推理入口均已支持 `auto: CUDA → MPS → CPU`；MPS 走稳定的 fp32 路径，CUDA 才启用 AMP。

## 5. 对 SegFormer 的验收线

后续 SegFormer-B2 必须基于同一 840 样本、固定划分和指标进行比较。最低目标：

- 五方向 Macro Dice 高于 0.8913 至少 3 个百分点；
- Keypoint F1 高于 0.7531 至少 5 个百分点；
- 任一主要方向通道 Dice 不下降超过 2 个百分点；
- 在固定困难集上单独报告 Macro Dice 与 Boundary F1。
