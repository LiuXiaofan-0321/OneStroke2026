# SegFormer-B2 v1：上云训练前检查单

目标：在不改动已冻结的 `benchmark-v1`（840 个可用样本，600 / 120 / 120 划分）的前提下，完成一次可复现、可解释的 SegFormer-B2 架构验证。

## 已完成的训练前准备

- SegFormer 使用 ImageNet 预训练归一化，而不是仅缩放到 `[0,1]`。
- 训练集启用标签安全增强：小幅平移、等比例缩放、亮度、对比度和模糊；所有几何变换同步作用到六个 mask。
- 显式禁用翻转和旋转。`vec1–vec5` 是方向相关通道，二者可能改变标签语义。
- 增加 3 epoch warm-up、余弦退火、梯度裁剪 `1.0`。
- 建立 B0 / B1 / B2 三组正交消融与真实 `512×512` smoke 配置。
- 增加验证集阈值校准脚本；test 集不参与阈值选择。

## 1. 云端环境与数据一致性

```bash
git clone https://github.com/LiuXiaofan-0321/OneStroke2026.git
cd OneStroke2026
git lfs install
git lfs pull
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[train]"
nvidia-smi
```

上传原始旧数据后，在云端重新生成 manifest 与划分；不要使用含本机绝对路径的 CSV：

```bash
python -m onestroke_model.scripts.audit_data \
  --data-root "<CLOUD_DATA_ROOT>/output_img" \
  --out-dir "./artifacts/data_audit"
python -m onestroke_model.scripts.build_splits \
  --manifest "./artifacts/data_audit/manifest.csv" \
  --output "./artifacts/data_audit/splits.csv"
```

必须确认：`840` 完整可用样本、`54` 异常样本、`600 / 120 / 120` 划分。若不一致，停止训练并先定位数据版本差异。

## 2. 先复评 U-Net，验证云端环境

```bash
python eval.py \
  --config "./configs/train_unet_rebaseline_v1.yaml" \
  --checkpoint "./checkpoints/unet_rebaseline_v1/best.pt" \
  --split test \
  --output "./artifacts/runs/unet_rebaseline_v1/cloud_test_metrics.json"
```

预期接近：Macro Dice `0.8913`、Keypoint F1 `0.7531`、Boundary F1 `0.7385`。明显不一致时，不进入 SegFormer。

## 3. 人工检查增强结果

```bash
python -m onestroke_model.scripts.preview_augmentations \
  --config "./configs/train_segformer_b2.yaml" \
  --output "./artifacts/segformer_augmentation_preview.png" \
  --num-samples 8
```

检查每一对原图/增强图：红色 mask overlay 是否仍覆盖正确笔画；没有裁掉关键端点；没有翻转或大旋转；背景/亮度变化不影响标签位置。若不通过，先收紧增强范围。

## 4. SegFormer-B2 smoke test

```bash
python train.py --config "./configs/train_segformer_b2_smoke.yaml"
```

该命令只运行一个训练 batch 和一个验证 batch，但会验证 Hugging Face 权重下载、显存、ImageNet 归一化、六通道前向/反向、边界损失、checkpoint 和指标。确认无 OOM、无 NaN 后才启动正式实验。

如果 24GB GPU 的 smoke test 显存充足，可将正式配置保持 `batch_size: 4`；若 OOM，改为 `batch_size: 2`，不改变其它实验条件。

## 5. 三组消融顺序

| 顺序 | 配置 | 唯一新增因素 | 目的 |
| --- | --- | --- | --- |
| B0 | `train_segformer_b2_v1_b0_base.yaml` | 无 | 方向类别加权 BCE + Dice；keypoint BCE + Dice；无边界损失 |
| B1 | `train_segformer_b2_v1_b1_keypoint.yaml` | Keypoint Focal + Dice | 验证稀疏 keypoint 的收益 |
| B2 | `train_segformer_b2.yaml` | Boundary Loss `0.2` | 验证交叉和端点边界增益 |

三组均使用同一 v1 数据、同一 seed、同一增强与同一学习率策略。每组先运行一个 seed。不要在 test 集据结果选择配置。

## 6. 验证集阈值校准与最终 test

每组训练完成后，只用 val 集寻找六个独立阈值：

```bash
python -m onestroke_model.scripts.calibrate_thresholds \
  --config "./configs/<EXPERIMENT>.yaml" \
  --checkpoint "./artifacts/runs/<EXPERIMENT>/checkpoints/best.pt" \
  --output "./artifacts/runs/<EXPERIMENT>/thresholds_val.json"
```

随后固定阈值，且只在 test 集评测一次：

```bash
python eval.py \
  --config "./configs/<EXPERIMENT>.yaml" \
  --checkpoint "./artifacts/runs/<EXPERIMENT>/checkpoints/best.pt" \
  --thresholds-json "./artifacts/runs/<EXPERIMENT>/thresholds_val.json" \
  --split test \
  --output "./artifacts/runs/<EXPERIMENT>/test_metrics.json"
```

选出 B0 / B1 / B2 中验证集表现最好的方案后，才用三个随机种子运行获胜配置；最终报告三个种子的均值和标准差。

## 7. 不在本轮做的工作

- 不把 SAM2 当作整字在线主模型；
- 不引入 GAN 合成数据；
- 不在 test 集调阈值、选模型或反复试参数；
- 不在 v1 阶段修改数据划分；
- 不把字体条件化、端侧蒸馏与本轮主分割实验混在一起。
