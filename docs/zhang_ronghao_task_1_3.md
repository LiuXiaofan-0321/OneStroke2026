# 论文 Task 1 修改版：QC-clean 主分割基准与 Character-disjoint 对照

负责人：张荣昊
对接人：刘小凡
发布日期：2026-08-13
任务状态：等待执行

> 这份文档替换旧版“任务 1/3”。旧版的 54 个缺标签样本复核和 U-Net
> 初步重测已经完成；现在的 **论文 Task 1** 是一项新的正式多模型比较任务。

## 1. 任务目标

在完全一致的数据、损失、训练策略、阈值标定和评测指标下，完成：

1. U-Net；
2. DeepLabV3+；
3. SegFormer-B2；

三种六通道分割模型的正式比较，并交付：

- 标准 QC-clean split 的主分割结果；
- 冻结 character-disjoint split 的未见字符泛化结果；
- 三随机种子的均值和样本标准差；
- 完整 checkpoint、日志、阈值、配置、环境与运行清单。

本任务不是为了追求某个模型“赢”，而是得到论文可以审计、复现和诚实报告的
主基准。负面结果也必须保留。

## 2. 数据口径已修改，禁止继续直接使用 840

旧数据恢复结论仍然成立：

```text
894 个样本目录
840 个文件完整的六通道 GT
54 个标签不完整样本（继续排除）
```

但完整文件不等于语义合格、也不等于独立观测。统一 QC 后：

```text
840 个完整 GT
- 12 个明确的原图/GT错配
- 59 个完全重复的非主实例
= 769 个 QC-clean 独立样本
```

12 个 mismatch 和 59 个 duplicate 没有重叠。

正式训练必须使用：

```text
artifacts/data_qc/manifest_qc_v1.csv
artifacts/data_qc/dataset_qc_exclusions_v1.csv
```

禁止使用：

```text
artifacts/data_recovery/manifest_resolved.csv  # 含 840 条，只用于取证
artifacts/data_audit/manifest.csv              # 旧口径
references/cache/segformer_b2_v1/              # 模型输出，绝不是 GT
```

固定哈希：

```text
QC-clean manifest SHA-256:
c55803a2381aa37e2a88c72b770be32036353e7b659986bf58f6591beba5edb4

QC exclusion SHA-256:
6397ed346618173edaef1e8146ec162836046fafb35869227a13a2c4ee6cc467
```

### 2.1 12 个原图/GT错配

判定口径：

```text
原图前景 与 五方向 GT 并集的 IoU < 0.80
```

样本：

```text
27/12
28/12
29/12
30/12
31/12
32/12
33/12
34/12
35/12
36/4
37/4
38/4
```

### 2.2 59 个完全重复非主实例

严格同时满足：

```text
image_pixel_sha256 完全相同
mask_content_sha256 完全相同
```

统计：

```text
55 个重复组
114 个成员
59 个冗余非主实例
52 个二元组、2 个三元组、1 个四元组
```

检测是全局进行的，不限制 `char_id`。

### 2.3 旧 B2 是否发生 train→test 精确重复泄漏

没有。

旧标准 600/120/120 split 中：

```text
54 个重复组全部在 train
1 个重复组全部在 val
test 无重复组
跨 train/val/test exact duplicate = 0
```

因此旧 B2 的 `0.9610` 不是被精确 train→test 重复直接抬高。但是旧训练集包含
12 个 mismatch 和 58 个重复副本，验证集也有 1 个重复副本，所以该结果只能作为
preliminary engineering evidence，不能代替本次正式论文基准。

## 3. 两套正式 split

## 3.1 标准 QC-clean split

保留原 600/120/120 样本分配，只应用冻结 QC 排除：

| Split | 原始数量 | QC-clean 数量 |
|---|---:|---:|
| Train | 600 | 530 |
| Validation | 120 | 119 |
| Test | 120 | 120 |

文件：

```text
artifacts/data_qc/standard_splits_qc_v1.csv
```

SHA-256：

```text
d79e48c264ac2b5431eb5543ddae798efc1542482e6ca76369eb78c155cc7b18
```

这套 split 用于论文的主分割比较。

## 3.2 Character-disjoint QC-clean split

原冻结字符分配不变：

```text
Train: 28 chars
Val:    6 chars
Test:   6 chars
```

原始字符分配 SHA-256 继续保留：

```text
eec9bf5c0910a2e9f6046991f1458519cd903d31deea3e0a4d33c555ff53a09e
```

在该分配之后应用同一 QC 排除清单，派生数量为：

| Split | 原始数量 | QC-clean 数量 |
|---|---:|---:|
| Train | 588 | 539 |
| Validation | 126 | 114 |
| Test | 126 | 116 |

文件：

```text
artifacts/data_qc/character_disjoint_splits_qc_v1.csv
artifacts/data_qc/character_disjoint_splits_qc_v1_report.json
```

派生 split SHA-256：

```text
e9303314d1b70d3f92efcdc5c0807f833148cbe64c2702379f0ac951ed2a1e2b
```

禁止重新随机分字符。QC 只是冻结后的排除层，不允许看模型结果后修改。

## 4. 你需要实现的部分

仓库已有：

- 六通道数据集和训练器；
- U-Net；
- SegFormer-B2；
- BCE/Dice/Focal/Boundary loss；
- validation-only threshold calibration；
- test evaluation；
- character-disjoint launcher；
- 三个待替换的 DeepLabV3+ 配置；
- 数据哈希和 QC 强制校验。

你主要需要完成：

### 4.1 DeepLabV3+

新增：

```text
src/onestroke_model/models/deeplabv3plus.py
```

并在：

```text
src/onestroke_model/models/factory.py
```

注册：

```text
model.name: deeplabv3plus
```

要求：

- 输入 `[B,3,H,W]`；
- 输出 logits `[B,6,H,W]`；
- 六通道独立 Sigmoid，模型内部不要 Softmax；
- 优先使用 ImageNet 预训练 encoder；
- 推荐 ResNet-50 backbone；
- ASPP + decoder 结构要明确；
- 输出恢复到输入空间大小；
- 不修改六通道含义：
  `vec1, vec2, vec3, vec4, vec5, keypoint`。

可以用成熟开源组件，但必须记录：

- 依赖包和版本；
- backbone；
- pretrained 权重来源；
- license；
- 参数量；
- 是否修改默认结构。

### 4.2 三随机种子

固定：

```text
20260811
314159
271828
```

不得看结果后删掉表现差的 seed。

正式论文目标：

| 模型 | 标准 split | Character-disjoint |
|---|---:|---:|
| U-Net | 3 seeds | 至少 1 seed；时间允许则 3 |
| DeepLabV3+ | 3 seeds | 3 seeds |
| SegFormer-B2 | 3 seeds | 3 seeds |

如果四天时间不足，优先级：

1. 标准 QC-clean：三模型各 3 seeds；
2. Character-disjoint：DeepLabV3+ 与 B2 各 3 seeds；
3. Character-disjoint：U-Net 补到 3 seeds。

任何减少必须在报告中写明原因，不能隐藏。

## 5. 公平比较规则

以下内容三模型必须一致：

- 输入尺寸：`512×512` 等比例填充；
- RGB 输入；
- 六通道多标签输出；
- 同一个 manifest；
- 同一个 split；
- 同一个 QC exclusion；
- 标签安全增强；
- loss 定义；
- validation-only threshold calibration；
- early stopping 只看 validation；
- test 只在模型与阈值固定后评测；
- 指标实现。

允许因模型结构而不同：

- batch size；
- encoder/decoder 分层学习率；
- normalization；
- 显存相关的 gradient accumulation。

不允许：

- 用 test 选择 epoch；
- 用 test 调阈值；
- 针对某模型单独删除困难样本；
- 为了漂亮数字改变 split、QC、指标或通道；
- 把模型生成的 reference mask 当 GT；
- 只提交最好 seed。

## 6. 训练和评测指标

主指标：

```text
五方向 Macro Dice
五方向 Macro IoU
Boundary F1
strict Keypoint F1
```

补充指标：

```text
每通道 Dice
每通道 IoU
每通道 Precision
每通道 Recall
Keypoint tolerant F1: 1 px / 3 px / 5 px
```

每个模型报告：

```text
mean
sample std
三个 seed 的原始值
```

不要只给最优一次。

## 7. 环境准备

```bash
git clone https://github.com/LiuXiaofan-0321/OneStroke2026.git
cd OneStroke2026
git lfs install
git lfs pull

python -m pip install -e ".[train,dev,paper]"
export PYTHONPATH="$PWD/src"
```

恢复后的原始 GT 不上传 GitHub。请从刘小凡处取得归档：

```text
OneStroke-main.tar.gz
```

固定归档 SHA-256：

```text
b9924007099033cc8b62128dc2139ea9cb04a66a48e56c46518407677254450d
```

恢复：

```bash
python -m onestroke_model.scripts.restore_legacy_gt \
  --archive "/path/to/OneStroke-main.tar.gz" \
  --destination "data/legacy_gt_v1/output_img" \
  --source-manifest "artifacts/data_recovery/source_manifest_identity_v1.csv" \
  --resolved-manifest "artifacts/data_recovery/manifest_resolved.csv" \
  --report "artifacts/data_recovery/verification_report.json"
```

仓库跟踪的 identity manifest 仅保留 894 个 sample ID、完整性和数组形状等
取证字段，不含历史机器绝对路径。恢复生成的正式 `manifest_qc_v1.csv` 使用
仓库相对路径。

恢复后先运行：

```bash
python -m onestroke_model.scripts.build_dataset_qc
```

输出必须与仓库固定哈希完全一致。如果不一致，停止训练并反馈，不要自行修正。

## 8. 开始训练前的强制检查

```bash
python - <<'PY'
from onestroke_model.config import load_yaml
from onestroke_model.data.data_contract import validate_data_contract

cfg = load_yaml(
    "configs/paper_ijdar/"
    "character_disjoint_segformer_b2_seed_20260811.yaml"
)
print(validate_data_contract(cfg["data"]))
PY
```

应看到：

```text
active_sample_count: 769
split_counts: train=539, val=114, test=116
qc_exclusion_count: 71
reference_cache_used_as_ground_truth: false
```

如果看到 840，说明还在用旧口径，禁止继续。

## 9. 标准 QC-clean 主基准

请为三种模型各建立三个标准 split 配置，建议命名：

```text
configs/paper_ijdar/main_qc_unet_seed_20260811.yaml
configs/paper_ijdar/main_qc_unet_seed_314159.yaml
configs/paper_ijdar/main_qc_unet_seed_271828.yaml

configs/paper_ijdar/main_qc_deeplabv3plus_seed_20260811.yaml
configs/paper_ijdar/main_qc_deeplabv3plus_seed_314159.yaml
configs/paper_ijdar/main_qc_deeplabv3plus_seed_271828.yaml

configs/paper_ijdar/main_qc_segformer_b2_seed_20260811.yaml
configs/paper_ijdar/main_qc_segformer_b2_seed_314159.yaml
configs/paper_ijdar/main_qc_segformer_b2_seed_271828.yaml
```

每个配置必须包含：

```yaml
data:
  manifest: artifacts/data_qc/manifest_qc_v1.csv
  splits: artifacts/data_qc/standard_splits_qc_v1.csv
  qc_exclusions: artifacts/data_qc/dataset_qc_exclusions_v1.csv
  expected_manifest_sha256: c55803a2381aa37e2a88c72b770be32036353e7b659986bf58f6591beba5edb4
  expected_splits_sha256: d79e48c264ac2b5431eb5543ddae798efc1542482e6ca76369eb78c155cc7b18
  expected_qc_exclusions_sha256: 6397ed346618173edaef1e8146ec162836046fafb35869227a13a2c4ee6cc467
  expected_split_counts:
    train: 530
    val: 119
    test: 120
```

每个 seed 的执行顺序：

```bash
python train.py --config "<config>"

python -m onestroke_model.scripts.calibrate_thresholds \
  --config "<config>" \
  --checkpoint "<run_dir>/checkpoints/best.pt" \
  --output "<run_dir>/thresholds_val.json"

python eval.py \
  --config "<config>" \
  --checkpoint "<run_dir>/checkpoints/best.pt" \
  --thresholds-json "<run_dir>/thresholds_val.json" \
  --split test \
  --output "<run_dir>/test_metrics.json"
```

## 10. Character-disjoint benchmark

仓库内 B2/U-Net 配置已经切换到 QC-clean split。DeepLabV3+ 当前配置名带：

```text
BLOCKED_BY_TASK1
```

实现并完成 smoke test 后：

1. 复制为不带 `BLOCKED_BY_TASK1` 的正式配置；
2. 删除 YAML 内 `research_status: BLOCKED_BY_TASK1`；
3. 保留固定 seed、数据路径和所有 SHA；
4. 更新 `src/onestroke_model/character_disjoint_runs.py` 中默认配置名；
5. 不改字符分配。

先 dry-run：

```bash
python -m onestroke_model.scripts.run_character_disjoint_benchmark
```

所有计划运行必须是 `READY`，然后才允许：

```bash
python -m onestroke_model.scripts.run_character_disjoint_benchmark --execute
```

## 11. Smoke test 要求

正式训练前，三模型都做一轮短 smoke test：

- 能读到正确数量；
- logits 为 `[B,6,512,512]`；
- loss 为有限值；
- AMP 可用；
- checkpoint 可保存和重新加载；
- threshold calibration 可运行；
- test 脚本能写 JSON；
- `data_contract` 被记录进输出。

Smoke 结果不得进入论文表格。

## 12. 交付目录

代码与小型文本制品提交到 GitHub；大 checkpoint 使用 Git LFS 或另行打包。

建议：

```text
artifacts/paper_ijdar/task1_main/
  run_manifest.json
  results_per_seed.csv
  results_summary.csv
  environment.json
  notes.md
  runs/
    <experiment_name>/
      run_metadata.json
      data_statistics.json
      metrics_history.json
      thresholds_val.json
      test_metrics.json
      benchmark.log
      checkpoints/best.pt
```

必须交付：

```text
src/onestroke_model/models/deeplabv3plus.py
src/onestroke_model/models/factory.py 的修改
正式 YAML 配置
DeepLabV3+ 单元测试
三模型逐 seed 指标
均值/标准差汇总
validation thresholds
训练日志
checkpoint SHA-256
环境版本
失败/异常说明
Git commit ID
```

## 13. 验收清单

- [ ] 使用 769 个 QC-clean 样本，而不是原始 840；
- [ ] exclusion SHA-256 完全一致；
- [ ] 标准 split 为 530/119/120；
- [ ] character-disjoint 为 539/114/116；
- [ ] 原字符分配 SHA 保留；
- [ ] DeepLabV3+ 是真实实现，不是名称占位；
- [ ] 输出六通道 logits，不用 Softmax；
- [ ] 三个 seed 都保留；
- [ ] threshold 只用 validation；
- [ ] test 不参与选择；
- [ ] 输出严格与容忍 keypoint 指标；
- [ ] 所有结果带 config/checkpoint/threshold/result 哈希；
- [ ] 没有把 reference cache 当 GT；
- [ ] 没有伪造或重建标签；
- [ ] 负面结果没有隐藏；
- [ ] 代码测试通过。

## 14. 遇到问题时反馈

请一次性提供：

```text
1. 执行命令
2. 完整报错文本
3. git rev-parse HEAD
4. Python/PyTorch/torchvision 版本
5. GPU 型号与显存
6. 使用的 config
7. validate_data_contract 输出
8. 对应日志路径
```

不要自行改变数据、split、QC、seed 或测试协议来绕过错误。
