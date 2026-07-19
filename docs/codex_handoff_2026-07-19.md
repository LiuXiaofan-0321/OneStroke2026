# OneStroke2026 模型模块：Codex 交接记录（2026-07-19）

> 用途：将本文件和仓库一并交给新的 Codex 账号。本文只记录项目状态与可复现命令；**不记录集群 IP、端口或密码**，这些信息由项目负责人在本地安全保存，绝不提交 GitHub。

## 1. 项目与当前目标

- 仓库：<https://github.com/LiuXiaofan-0321/OneStroke2026>
- 本地仓库：`C:\University Courses\大创项目\model_module`
- 默认分支：`main`
- 最近已推送提交：`5acaee3 Prepare controlled SegFormer v1 experiments`
- 当前日期：2026-07-19

项目是书法汉字笔画多标签分割。模型输入 RGB 汉字图像，等比例 padding/resize 到 `512×512`；输出六张独立概率图：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

交叉处允许多通道重叠，因此六通道使用 **独立 Sigmoid**，禁止 Softmax。当前 7 月主线是完整汉字分割高精度教师模型；字体条件化、端侧蒸馏、QAT/剪枝、ONNX/App 联调均不在本轮主实验中。

## 2. 已确定的技术路线

1. **可信旧基线**：旧 U-Net 只复用标签逻辑和权重，训练/评测在新框架中重建。
2. **云端主线**：ImageNet 预训练的 SegFormer-B2，替换为六通道多标签头。
3. **消融顺序**：
   - B0：方向通道加权 BCE + Dice；keypoint BCE + Dice；无 boundary loss。
   - B1：B0 + keypoint Focal + Dice。
   - B2：B1 + boundary loss，权重 `0.2`。
4. **SAM2**：仅作为后续受控辅助实验（例如标注/边界/实例研究），不是小数据集下的线上主模型，也不要为它阻塞 SegFormer。
5. **未来双模型**：8 月再将云端教师蒸馏到 SegFormer-B0/MobileNetV3 端侧学生；现在不要混入这一工作。

## 3. 数据版本与审计结果

冻结数据版本是旧 OneStroke `output_img` 数据。云端已上传的原始数据根目录：

```text
~/lxf/data/output_img
```

2026-07-14 在云端运行 `audit_data` 的结果为：

```text
num_char_dirs: 43
num_samples: 894
num_samples_with_errors: 54
num_samples_missing_any_mask: 54
num_complete_samples: 840
```

这与本地审计结果一致。54 个异常样本均缺少 mask，应由 manifest 自动排除，不能手动补零标签。固定划分目标为：

```text
train / val / test = 600 / 120 / 120
```

用户已回复划分“没问题了”，但新的接手者应在云端复核：

```bash
cd ~/lxf/OneStroke2026
cat artifacts/data_audit/splits_report.json
```

云端 manifest 与 split 位置：

```text
~/lxf/OneStroke2026/artifacts/data_audit/manifest.csv
~/lxf/OneStroke2026/artifacts/data_audit/splits.csv
```

**不要使用本地生成的 CSV 上传到云端**，其中含本机绝对路径。云端必须从上传的原始数据重新生成 audit/manifest/split。

## 4. 已完成的代码与实验准备

### 4.1 U-Net 可信基线

张荣昊已完成任务 1、3 和可信 U-Net 重测。结果记录于：

- `docs/unet_rebaseline_report_2026-07-12.md`
- `configs/train_unet_rebaseline_v1.yaml`
- `checkpoints/unet_rebaseline_v1/best.pt`（Git LFS）

基线指标：

```text
Macro Dice    0.8913
Macro IoU     0.8049
Keypoint F1   0.7531
Boundary F1   0.7385
```

云端完成 `git clone` 后必须执行：

```bash
git lfs install
git lfs pull
```

否则 checkpoint 只是 LFS 指针文件。

### 4.2 SegFormer 上云前准备（已推送）

提交 `5acaee3` 已包含：

- SegFormer ImageNet 归一化；
- 标签安全增强：小幅平移、缩放、亮度、对比度、模糊；同步作用于六个 mask；
- 显式禁用旋转、翻转（它们会破坏方向通道语义）；
- AdamW、混合精度、编码器/解码器分层学习率、3 epoch warm-up、余弦退火、梯度裁剪；
- keypoint 可选 BCE 或 Focal + Dice；
- boundary loss；
- B0/B1/B2 三组正式配置和一个真实 `512×512` smoke 配置；
- 只用验证集的阈值校准脚本；
- 增强效果预览脚本；
- 上云检查单：`docs/segformer_v1_preflight.md`。

关键配置：

| 用途 | 配置 | 输出目录 |
| --- | --- | --- |
| Smoke | `configs/train_segformer_b2_smoke.yaml` | `artifacts/runs/segformer_b2_v1_smoke` |
| B0 | `configs/train_segformer_b2_v1_b0_base.yaml` | `artifacts/runs/segformer_b2_v1_b0_base` |
| B1 | `configs/train_segformer_b2_v1_b1_keypoint.yaml` | `artifacts/runs/segformer_b2_v1_b1_keypoint` |
| B2 | `configs/train_segformer_b2.yaml` | `artifacts/runs/segformer_b2_v1_b2_boundary` |

正式 SegFormer-B2 默认是 `image_size=512`、`batch_size=4`、`num_workers=4`、`amp=true`。单张 A100-40GB 足够；不要一开始上 DataParallel。

### 4.3 人工困难集

- 已生成困难样本候选图：`artifacts/data_audit/hardset_candidates.png`。
- 项目负责人已完成人工复核；相关说明见 `docs/liuxiaofan_task_2_hardset.md`。
- 当前本地工作区还有未跟踪的 Excel/备份 CSV：`reviews/hardset_review_前20行初审完成.csv`，不要误删或强制覆盖。

## 5. 云端实际状态（最重要）

项目负责人使用集群共享账号 `xiaohe`。目录被统一放入个人工作根：

```text
~/lxf/
├── OneStroke2026/     # Git 仓库、artifacts、logs
├── data/output_img/   # 原始数据
├── venvs/onestroke/   # Python 3.11 virtualenv
└── cache/             # pip / Hugging Face / PyTorch cache
```

环境已安装：

```bash
source ~/lxf/venvs/onestroke/bin/activate
export PIP_CACHE_DIR=~/lxf/cache/pip
export HF_HOME=~/lxf/cache/huggingface
export TORCH_HOME=~/lxf/cache/torch
```

集群已确认：

- Slurm 分区：`a100`
- 40GB A100 GRES：`gpu:NVIDIAA100-PCIE-40GB:2`（申请单卡时写 `:1`）
- 共享账号上已有大量其他人的运行/排队任务；**严禁取消不确定归属的任务**。
- 可用性依赖队列优先级。交互式 `srun` 被用户以 `Ctrl+C` 取消过一次，任务号是 `3075595`，无需处理。

### 已提交但尚未核验的 smoke job

用户随后提交了以下 Slurm job：

```text
job id: 3075597
job name: onestroke-smoke
```

该 job 会依次执行：`nvidia-smi`、PyTorch CUDA 检查、U-Net test 复测、SegFormer smoke test。该任务在 2026-07-13 提交，之后用户没有提供日志或最终状态。现在已经是 2026-07-19，**不要假定成功，先检查记录**：

```bash
squeue -j 3075597
sacct -j 3075597 --format=JobID,JobName%24,State,Elapsed,ExitCode
tail -n 120 ~/lxf/OneStroke2026/logs/onestroke-smoke_3075597.out
tail -n 120 ~/lxf/OneStroke2026/logs/onestroke-smoke_3075597.err
```

若 `sacct` 不可用，使用：

```bash
ls -lh ~/lxf/OneStroke2026/logs/onestroke-smoke_3075597.*
```

判定 smoke 通过的条件：

1. `nvidia-smi` 显示 A100；
2. `torch.cuda.is_available()` 为 `True`；
3. U-Net 指标接近 Macro Dice `0.8913`、Keypoint F1 `0.7531`、Boundary F1 `0.7385`；
4. SegFormer smoke 没有 CUDA OOM、NaN、预训练权重下载失败或 checkpoint 写入失败。

若 smoke job 因队列被取消/从未开始，重新提交一份，不要改数据或训练配置。

## 6. 推荐的下一步执行顺序

### Step A：核验 smoke job

先按第 5 节检查 `3075597`。如需重提，可在登录节点执行：

```bash
cd ~/lxf/OneStroke2026
mkdir -p logs

sbatch -p a100 \
  --gres=gpu:NVIDIAA100-PCIE-40GB:1 \
  --cpus-per-task=8 \
  --mem=32G \
  --time=02:00:00 \
  --job-name=onestroke-smoke \
  --output=logs/onestroke-smoke_%j.out \
  --error=logs/onestroke-smoke_%j.err \
  --wrap="bash -lc 'set -e; export PIP_CACHE_DIR=~/lxf/cache/pip; export HF_HOME=~/lxf/cache/huggingface; export TORCH_HOME=~/lxf/cache/torch; source ~/lxf/venvs/onestroke/bin/activate; cd ~/lxf/OneStroke2026; nvidia-smi; python -c \"import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))\"; python eval.py --config ./configs/train_unet_rebaseline_v1.yaml --checkpoint ./checkpoints/unet_rebaseline_v1/best.pt --split test --output ./artifacts/runs/unet_rebaseline_v1/cloud_test_metrics.json; python train.py --config ./configs/train_segformer_b2_smoke.yaml'"
```

记录 `Submitted batch job <JOB_ID>` 输出。之后可安全关闭 SSH/Xshell；Slurm job 不会随会话断开而停止。

### Step B：人工确认增强

在已分配到 GPU 的会话/小作业里运行：

```bash
cd ~/lxf/OneStroke2026
source ~/lxf/venvs/onestroke/bin/activate
python -m onestroke_model.scripts.preview_augmentations \
  --config ./configs/train_segformer_b2.yaml \
  --output ./artifacts/segformer_augmentation_preview.png \
  --num-samples 8
```

把 PNG 取回本地或通过远程文件工具查看。检查：mask overlay 仍与笔画对齐、关键端点没有被裁掉、没有翻转或大旋转、背景变化没有改变标签位置。若不通过，收紧增强范围后重新 smoke。

### Step C：按 B0 → B1 → B2 依次训练

**不要并行或提前查看 test 集选模型。** 每组使用同一个 v1 数据、划分和 seed；结束后仅在 val 校准阈值和比较。

B0 的后台提交模板：

```bash
cd ~/lxf/OneStroke2026
mkdir -p logs

sbatch -p a100 \
  --gres=gpu:NVIDIAA100-PCIE-40GB:1 \
  --cpus-per-task=8 \
  --mem=32G \
  --time=08:00:00 \
  --job-name=segformer-b0 \
  --output=logs/segformer-b0_%j.out \
  --error=logs/segformer-b0_%j.err \
  --wrap="bash -lc 'set -e; export PIP_CACHE_DIR=~/lxf/cache/pip; export HF_HOME=~/lxf/cache/huggingface; export TORCH_HOME=~/lxf/cache/torch; source ~/lxf/venvs/onestroke/bin/activate; cd ~/lxf/OneStroke2026; nvidia-smi; python train.py --config ./configs/train_segformer_b2_v1_b0_base.yaml'"
```

查看某个作业：

```bash
squeue -j <JOB_ID>
tail -f ~/lxf/OneStroke2026/logs/segformer-b0_<JOB_ID>.out
```

**只取消自己确认创建的 job：**

```bash
scancel <JOB_ID>
```

每组训练完成后，在 GPU 会话/短作业中依次运行验证集阈值校准和验证集评测。以 B0 为例：

```bash
cd ~/lxf/OneStroke2026
source ~/lxf/venvs/onestroke/bin/activate

python -m onestroke_model.scripts.calibrate_thresholds \
  --config ./configs/train_segformer_b2_v1_b0_base.yaml \
  --checkpoint ./artifacts/runs/segformer_b2_v1_b0_base/checkpoints/best.pt \
  --output ./artifacts/runs/segformer_b2_v1_b0_base/thresholds_val.json

python eval.py \
  --config ./configs/train_segformer_b2_v1_b0_base.yaml \
  --checkpoint ./artifacts/runs/segformer_b2_v1_b0_base/checkpoints/best.pt \
  --thresholds-json ./artifacts/runs/segformer_b2_v1_b0_base/thresholds_val.json \
  --split val \
  --output ./artifacts/runs/segformer_b2_v1_b0_base/val_metrics.json
```

对 B1/B2 替换 config 和相应 output directory 即可。根据 **val 指标** 选择获胜配置；之后才对获胜模型固定阈值、运行一次 test 评测。最终获胜方案需要运行 3 个随机种子，报告均值、标准差和逐类指标。

## 7. 本轮验收标准

与重测 U-Net 相比，最终模型需要达到：

- 五方向 Macro Dice 至少提升 3 个百分点；
- Keypoint F1 至少提升 5 个百分点；
- 任一主要方向通道不得下降超过 2 个百分点；
- 困难集 Macro Dice 至少提升 5 个百分点；
- 30 个代表结果经书法成员复核，无明显系统性错分；
- 训练、评测、单图推理可在干净环境中单命令复现。

## 8. Git 与协作注意事项

当前本地工作区在本文件创建前已存在用户改动，不能随意重置：

```text
M  docs/zhang_ronghao_task_1_3.md
?? reviews/hardset_review_前20行初审完成.csv
```

这些内容不是本交接工作产生的。不要使用 `git reset --hard`、`git checkout -- .` 或覆盖队友修改。新文档本身尚未自动提交；如项目负责人希望同步到 GitHub，请在确认差异后只提交本文件。

推荐先检查：

```bash
git status --short
git log --oneline -5
```

## 9. 重要边界与常见误区

- 不要把集群密码、IP、端口、数据集或大 checkpoint 上传到 GitHub。
- `git lfs pull` 是获得 U-Net checkpoint 的必要步骤。
- `srun` 是交互式资源申请；按 `Ctrl+C` 会取消排队。长训练一律用 `sbatch`，可安全关闭 Xshell。
- `squeue` 中账号名相同的其他训练可能属于队友；只操作自己刚提交且已记录 job id 的任务。
- 方向通道不能随意做翻转或旋转增强；这会让 `vec1–vec5` 的标签语义错位。
- 不要用 test 集调阈值、挑配置或反复试参；阈值仅从 val 集获得。
- 字体选择功能是未来的条件化/泛化方向；当前核心分割 v1 先稳定产出可复现实验结果。

## 10. 相关文档索引

- `docs/segformer_v1_preflight.md`：上云训练前检查单与 B0/B1/B2 流程。
- `docs/unet_rebaseline_report_2026-07-12.md`：可信 U-Net 基线指标。
- `docs/font_aware_model_plan.md`：字体选择功能加入后的长期模型规划。
- `docs/postdoc_progress_report_2026-07-11.md`：向博士后汇报的项目背景与路线。
- `docs/liuxiaofan_task_2_hardset.md`：困难集人工复核任务说明。
- `README.md`：安装、训练、评测、推理的入口说明。
