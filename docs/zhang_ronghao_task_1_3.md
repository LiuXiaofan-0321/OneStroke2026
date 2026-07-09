# 张荣昊阶段任务：数据问题复核 + U-Net 重测基线

负责人：张荣昊  
协作对象：刘小凡  
任务时间：建议 7 月 9–13 日优先完成  
任务范围：只做数据审计复核和 U-Net baseline，不改 SegFormer/SAM2 主线代码，避免和主模型开发互相影响。

## 0. 当前背景

当前模型工程已经建立为独立 GitHub 仓库。请先从 GitHub 克隆项目，再进入项目目录：

```powershell
git clone <GITHUB_REPO_URL>
cd model_module
```

已有内容：

- 数据审计脚本
- 固定六通道 schema：`vec1, vec2, vec3, vec4, vec5, keypoint`
- `manifest.csv` 生成逻辑
- `splits.csv` 固定划分逻辑
- U-Net baseline 训练入口
- 评测入口

旧数据初步审计结果：

```text
字符目录：43
总样本：894
完整可用样本：840
存在问题样本：54
固定划分：
  train: 600
  val:   120
  test:  120
```

你这阶段优先做两个任务：

1. 复核 54 个问题样本。
2. 跑 U-Net 重测基线。

这两个任务和刘小凡的 SegFormer-B2 / SAM2 主线互不阻塞。

## 1. 环境准备

进入模型工程目录：

```powershell
cd model_module
```

建议新建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

安装基础依赖：

```powershell
python -m pip install -e .
```

如果要训练 U-Net，需要安装训练依赖：

```powershell
python -m pip install -e ".[train]"
```

如果 PyTorch 安装失败，先记录错误信息，不要长时间卡住，可以把报错发给刘小凡一起处理。

## 2. 任务一：复核旧数据问题样本

### 2.1 任务目标

确认 `manifest.csv` 中 `errors` 不为空的样本到底是什么问题，判断是否能修复，以及是否应该从训练集中剔除。

这一步的意义：

- 防止坏数据进入训练。
- 防止 U-Net / SegFormer 指标被错误标签影响。
- 为后续报告提供可信的数据审计说明。

### 2.2 输入文件

主要输入：

```text
artifacts/data_audit/manifest.csv
artifacts/data_audit/audit_report.json
```

如果你本地还没有这些文件，先重新生成：

```powershell
python -m onestroke_model.scripts.audit_data `
  --data-root "你的旧OneStroke数据路径\StrokeSegmentation\data\output_img" `
  --out-dir ".\artifacts\data_audit"

python -m onestroke_model.scripts.build_splits `
  --manifest ".\artifacts\data_audit\manifest.csv" `
  --output ".\artifacts\data_audit\splits.csv"
```

注意：`--data-root` 要换成你本机旧数据真实路径。

### 2.3 具体操作

打开：

```text
artifacts/data_audit/manifest.csv
```

筛选：

```text
errors != 空
```

逐个查看 54 个问题样本。

重点检查：

- 原图是否存在。
- 原图能否正常打开。
- `mask_1.npy` 是否存在。
- `mask_2.npy` 是否存在。
- `mask_3.npy` 是否存在。
- `mask_4.npy` 是否存在。
- `mask_5.npy` 是否存在。
- `mask_key_point.npy` 是否存在。
- `0.npy` 六通道堆叠标签是否存在。
- mask 尺寸是否和其他通道一致。
- 文件是否损坏。

### 2.4 问题类型定义

建议把问题归为以下几类：

| error_type | 含义 |
| --- | --- |
| `missing_image` | 原图缺失 |
| `bad_image` | 原图损坏或无法读取 |
| `missing_mask` | 某个通道 mask 缺失 |
| `bad_mask` | `.npy` mask 损坏或无法读取 |
| `shape_mismatch` | 多个 mask 尺寸不一致 |
| `empty_mask` | 标签为空，需要判断是否合理 |
| `unknown` | 暂时无法判断 |

### 2.5 是否修复的判断标准

可以修复：

- 缺少 `0.npy`，但六个独立 mask 都存在，可以后续重新堆叠。
- 某个文件路径或命名明显错误，但能从同目录找到正确文件。
- 单个样本的附属文件缺失，但不影响六通道标签，可以记录后继续使用。

不建议修复：

- 原图缺失。
- 关键 mask 缺失且无法从其他文件恢复。
- mask 文件损坏。
- mask 尺寸严重异常。
- 不确定标签是否正确。

原则：

> 宁可少用一部分不可靠数据，也不要把错误标签混进训练集。

### 2.6 输出文件

创建：

```text
artifacts/data_audit/bad_samples_review.csv
```

建议字段：

```text
sample_id
char_id
sample_index
image_path
original_errors
error_type
can_fix
fix_method
decision
reviewer
notes
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `sample_id` | 样本 ID，例如 `0/12` |
| `char_id` | 字符目录 ID |
| `sample_index` | 样本编号 |
| `image_path` | 原图路径 |
| `original_errors` | manifest 里的原始错误 |
| `error_type` | 归类后的错误类型 |
| `can_fix` | `yes` / `no` / `uncertain` |
| `fix_method` | 如果能修复，写修复方法 |
| `decision` | `keep` / `fix_then_keep` / `drop` / `need_discussion` |
| `reviewer` | 填你的名字 |
| `notes` | 备注 |

### 2.7 任务一验收标准

完成后应能回答：

- 54 个问题样本分别是什么问题。
- 有多少可以修复。
- 有多少必须剔除。
- 是否存在系统性数据生成 bug。
- 是否需要重新生成部分标签。

最终交付：

```text
artifacts/data_audit/bad_samples_review.csv
```

## 3. 任务三：U-Net 重测基线

### 3.1 任务目标

使用新工程、新数据划分、新指标，重新训练和评测 U-Net baseline。

这一步不是为了证明 U-Net 很强，而是为了建立一个可信对照：

> 后续 SegFormer-B2 必须在这个重测 baseline 上明显提升。

### 3.2 训练前检查

确认以下文件存在：

```text
artifacts/data_audit/manifest.csv
artifacts/data_audit/splits.csv
configs/train_unet.yaml
train.py
eval.py
```

确认 `splits.csv` 里大致是：

```text
train: 600
val:   120
test:  120
```

如果你的数据路径不同，需要先重新生成 manifest 和 splits。

### 3.3 安装训练依赖

```powershell
cd model_module
python -m pip install -e ".[train]"
```

确认 PyTorch：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

如果 `torch.cuda.is_available()` 是 `False`，可以先用 CPU 做 smoke test，但正式训练建议用 GPU。

### 3.4 Smoke test

先不要一上来跑满 80 epoch。建议先把 `configs/train_unet.yaml` 临时复制一份：

```text
configs/train_unet_smoke.yaml
```

把里面的 epoch 改小，例如：

```yaml
optim:
  epochs: 1
```

然后运行：

```powershell
python train.py --config ".\configs\train_unet_smoke.yaml"
```

确认：

- 能正确读取数据。
- 能开始训练。
- loss 不为 NaN。
- 能保存 checkpoint。

Smoke test 只是环境检查，不作为正式结果。

### 3.5 正式训练

运行：

```powershell
python train.py --config ".\configs\train_unet.yaml"
```

默认输出目录：

```text
artifacts/runs/unet_rebaseline
```

重点观察：

- loss 是否稳定下降。
- val Macro Dice 是否上升。
- keypoint F1 是否极低。
- 是否 early stopping。
- 是否出现显存不足。

### 3.6 正式评测

训练完成后运行：

```powershell
python eval.py `
  --config ".\configs\train_unet.yaml" `
  --checkpoint ".\artifacts\runs\unet_rebaseline\checkpoints\best.pt" `
  --split test `
  --output ".\artifacts\runs\unet_rebaseline\test_metrics.json"
```

如果需要评测 val：

```powershell
python eval.py `
  --config ".\configs\train_unet.yaml" `
  --checkpoint ".\artifacts\runs\unet_rebaseline\checkpoints\best.pt" `
  --split val `
  --output ".\artifacts\runs\unet_rebaseline\val_metrics.json"
```

### 3.7 需要记录的指标

至少记录：

```text
macro_dice
macro_iou
keypoint_f1
每通道 dice
每通道 iou
每通道 precision
每通道 recall
```

通道顺序固定：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

### 3.8 训练记录文档

创建：

```text
artifacts/runs/unet_rebaseline/notes.md
```

建议内容：

```markdown
# U-Net Rebaseline Notes

## Environment

- Date:
- Machine:
- GPU:
- Python:
- PyTorch:

## Data

- manifest:
- splits:
- train/val/test counts:

## Config

- config:
- image_size:
- batch_size:
- epochs:
- lr:
- loss:

## Results

- best epoch:
- val macro dice:
- test macro dice:
- test macro iou:
- test keypoint f1:

## Observations

- loss 是否稳定下降：
- keypoint 是否难学：
- 哪些字符失败较多：
- 哪些通道失败较多：

## Problems

- 训练中遇到的问题：
- 需要刘小凡确认的问题：
```

### 3.9 任务三交付物

必须交付：

```text
artifacts/runs/unet_rebaseline/checkpoints/best.pt
artifacts/runs/unet_rebaseline/test_metrics.json
artifacts/runs/unet_rebaseline/notes.md
```

如果时间允许，额外交付：

```text
artifacts/runs/unet_rebaseline/val_metrics.json
artifacts/runs/unet_rebaseline/failure_cases.csv
artifacts/runs/unet_rebaseline/preview_images/
```

注意：

- checkpoint 文件不要直接提交到 GitHub，除非团队明确使用 Git LFS 或网盘。
- `artifacts/` 默认被 `.gitignore` 忽略，这是正常的。
- 结果可以先通过压缩包、网盘或截图同步。

### 3.10 任务三验收标准

完成后应能回答：

- U-Net 在新划分下的正式 Macro Dice 是多少。
- keypoint F1 是多少。
- 哪几个通道表现最差。
- 是否复现了旧项目大致表现。
- 后续 SegFormer-B2 至少需要提升多少才算有效。

## 4. 和刘小凡的分工边界

你这阶段主要负责：

- 数据问题样本复核。
- U-Net baseline 训练。
- U-Net 结果记录。
- 把发现的问题整理清楚。

刘小凡同步负责：

- SegFormer-B2 主线模型。
- SAM2 数据格式和训练方案。
- 字体选择接口与 `target_style_id` 设计。
- 云端/端侧双模型路线。

避免互相影响：

- 你暂时不要改 `src/onestroke_model/models/segformer.py`。
- 你暂时不要改 `configs/train_segformer_b2.yaml`。
- 如果需要改 `train.py` 或 `eval.py`，先说明原因。
- 你可以在 `artifacts/` 下自由生成实验结果。

## 5. 遇到问题时优先反馈这些信息

如果训练或数据检查出问题，请不要只说“跑不了”，尽量附上：

```text
1. 执行的命令
2. 完整报错截图或文本
3. 当前所在目录
4. Python 版本
5. PyTorch 版本
6. 是否有 GPU
7. 出问题的 sample_id，如果是数据问题
```

这样能更快定位问题。
