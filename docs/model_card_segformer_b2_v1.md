# SegFormer-B2 v1 模型卡

版本：`segformer-b2-v1`

冻结日期：2026-07-26

定位：云端高精度六通道分割模型、后续蒸馏教师候选

## 1. 能力边界

本版本接收一张完整汉字 RGB 图像，输出固定顺序的六通道概率图与二值掩码：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

六个通道使用独立 Sigmoid，交叉区域允许多通道重叠。推理结果会恢复到输入图片原始尺寸。

本版本支持：

- 五方向笔画区域分割；
- 关键点区域定位；
- 六通道 mask、叠加图和关键点连通域中心坐标导出。

本版本不支持：

- 按书家或字体进行条件化推理；
- 字体相似度或书法质量评分；
- 自然语言评语；
- OCR 和笔顺恢复。

接口必须根据 `capabilities` 展示能力。当前 `style_conditioning=false`、`style_scoring=false`，不得向用户显示伪造的字体评分。

## 2. 模型与训练

- 主干：ImageNet/ADE20K 预训练 SegFormer-B2；
- 输入：RGB，白底等比例填充到 `512x512`，ImageNet normalization；
- 输出：六通道 logits；
- 方向损失：类别加权 BCE + Dice；
- 关键点损失：Focal + Dice；
- 边界损失权重：`0.2`；
- 优化器：AdamW；
- 编码器学习率：`3e-5`；
- 解码器学习率：`3e-4`；
- 调度：3 epoch warmup + cosine；
- checkpoint 选择：验证集五方向 Macro Dice；
- 最佳 checkpoint：epoch 71。

训练配置见 `configs/train_segformer_b2_v1_b2_boundary.yaml`。

## 3. 数据与划分

- 原始目录：43 个字符、894 个样本；
- 完整六通道标签：840 个样本；
- 固定划分：训练 600、验证 120、测试 120；
- 测试集不参与阈值搜索；
- 缺少可靠书写者身份，因此当前划分按固定样本序号分组。

最后一点意味着测试结果可以衡量固定来源分组上的泛化，但不能等同于严格的“未见书写者”结论。

## 4. 测试结果

| 模型 | Macro Dice | Macro IoU | Keypoint F1 | Boundary F1 |
| --- | ---: | ---: | ---: | ---: |
| U-Net 重测 | 0.891350 | 0.804875 | 0.753010 | 0.738529 |
| SegFormer-B2 B0 | 0.955282 | 0.914415 | 0.713028 | 0.808364 |
| SegFormer-B2 B1 | 0.955414 | 0.914657 | 0.713854 | 0.807672 |
| **SegFormer-B2 B2** | **0.961049** | **0.925051** | **0.715935** | **0.834753** |

B2 相比 U-Net：

- 五方向 Macro Dice 提升约 6.97 个百分点；
- Boundary F1 提升约 9.62 个百分点；
- 严格逐像素 Keypoint F1 下降约 3.71 个百分点。

因此 B2 被选为方向分割与边界质量最优模型，但没有达到“Keypoint F1 相比 U-Net 提升 5 个百分点”的原定验收条件。

## 5. 关键点诊断

在固定 120 个测试样本上重新推理：

| 允许定位偏差 | Keypoint F1 |
| --- | ---: |
| 0 像素 | 0.7160 |
| 1 像素 | 0.8997 |
| 3 像素 | 0.9284 |
| 5 像素 | 0.9354 |

120 个样本均有预测；严格 F1 低于 0.5 的样本为 1 个，5 像素容差 F1 低于 0.8 的样本为 4 个。样本检查表明主要误差来自极小关键点区域的边缘偏移，而不是整组关键点缺失。

严格逐像素 F1 仍作为正式指标，容差指标仅补充说明实际定位能力。下游若使用关键点坐标，应采用连通域中心并允许 3 至 5 像素匹配容差。

## 6. 固定阈值

阈值只在验证集上校准：

| 通道 | 阈值 |
| --- | ---: |
| vec1 | 0.9108889 |
| vec2 | 0.8713334 |
| vec3 | 0.9108889 |
| vec4 | 0.9306667 |
| vec5 | 0.9306667 |
| keypoint | 0.2582222 |

## 7. 推理命令

安装：

```powershell
git lfs install
git lfs pull
python -m pip install -e ".[train]"
```

导出完整开发资源：

```powershell
python infer.py `
  --config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --image ".\demo.png" `
  --output-dir ".\artifacts\demo_b2" `
  --model-version "segformer-b2-v1"
```

输出：

```text
result.json
prediction.npz
mask_vec1.png ... mask_vec5.png
mask_keypoint.png
overlay.png
```

正式测试集评测：

```powershell
python eval.py `
  --config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --manifest ".\artifacts\data_audit\manifest.csv" `
  --splits ".\artifacts\data_audit\splits.csv" `
  --split test `
  --output ".\artifacts\b2_test_metrics.json"
```

`manifest.csv` 中的图像和标签路径由数据准备环境提供，不随 checkpoint 上传。若 manifest 是另一台机器生成的绝对路径，使用 `--manifest` 和 `--splits` 指向当前环境的固定文件。

部署时模型由 checkpoint 离线构建，不需要访问 Hugging Face。只有重新训练并加载预训练权重时才需要联网。

## 8. 版本与完整性

- checkpoint：`checkpoints/segformer_b2_v1/best.pt`
- 大小：328,624,482 bytes
- SHA-256：`64df27aafc0eeecc07c0ac52c6ff00eef6b290ae7baf964cd5cf786262f395ce`
- schema：`releases/segformer_b2_v1/schema.json`
- 版本清单：`releases/segformer_b2_v1/model_manifest.json`

## 9. 已知限制

- 数据只有 840 个完整样本，覆盖 43 个字符；
- 没有可靠 writer ID，不能证明对未见书写者的泛化；
- 当前图像主要来自旧项目采集流程，新纸张背景、拍照噪声和真实移动端输入尚未系统测试；
- 关键点严格逐像素 F1 低于 U-Net；
- 当前仅完成单随机种子 B0/B1/B2 消融，没有三随机种子均值和标准差；
- 当前 checkpoint 是云端教师候选，不代表最终端侧模型。

后续字体条件化、字体评分和语言反馈应作为独立版本开发，不修改本版本的能力声明和历史指标。
