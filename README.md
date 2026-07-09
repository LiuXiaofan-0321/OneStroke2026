# “一笔成章”模型模块

本目录是 2026 年项目的独立模型工程。旧 OneStroke 仓库只作为数据、标签和 U-Net 权重来源参考，不继承旧训练框架。

## 当前阶段目标

7 月 9 日前先完成数据与评测地基：

- 审计旧数据目录，生成 `manifest.csv`
- 固定 `train/val/test` 划分，生成 `splits.csv`
- 固定六通道 schema：`vec1, vec2, vec3, vec4, vec5, keypoint`
- 为 U-Net 重测基线、SegFormer-B2 主线和 SAM2 受控实验准备统一入口

## 重要设计文档

- [字体选择功能下的模型模块推进计划](docs/font_aware_model_plan.md)

## 推荐目录

```text
model_module/
  configs/              # 数据、训练、模型配置
  src/onestroke_model/  # Python 包源码
  scripts/              # 命令行脚本
  artifacts/            # 生成的 manifest、split、报告、checkpoint（默认不提交）
```

## 安装

建议 Python 3.11。先进入本目录：

```powershell
cd "C:\University Courses\大创项目\model_module"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[train]"
```

如果只是先跑数据审计，基础依赖即可：

```powershell
python -m pip install -e .
```

## 1. 生成数据审计与 manifest

将 `--data-root` 指向旧仓库的 `StrokeSegmentation/data/output_img`：

```powershell
python -m onestroke_model.scripts.audit_data `
  --data-root "C:\path\to\OneStroke\StrokeSegmentation\data\output_img" `
  --out-dir ".\artifacts\data_audit"
```

输出：

- `artifacts/data_audit/manifest.csv`
- `artifacts/data_audit/audit_report.json`

## 2. 固定划分

```powershell
python -m onestroke_model.scripts.build_splits `
  --manifest ".\artifacts\data_audit\manifest.csv" `
  --output ".\artifacts\data_audit\splits.csv"
```

默认优先使用 `writer_id/source_id`；没有身份信息时使用旧数据的 `sample_index` 作为分组键，避免同一批来源跨 train/val/test 泄漏。

## 3. 生成困难样本模板

```powershell
python -m onestroke_model.scripts.make_hardset_template `
  --manifest ".\artifacts\data_audit\manifest.csv" `
  --output ".\artifacts\data_audit\hardset_template.csv" `
  --limit 50
```

该文件用于人工标记困难类型：交叉、粘连、端点、线宽、背景等。

## 训练、评测和推理入口

安装 `.[train]` 后可以直接运行 U-Net 或 SegFormer 配置：

```powershell
python train.py --config ".\configs\train_unet.yaml"
python eval.py --config ".\configs\train_unet.yaml" --checkpoint ".\artifacts\checkpoints\best.pt"
python infer.py --config ".\configs\train_segformer_b2.yaml" --checkpoint ".\artifacts\checkpoints\best.pt" --image ".\demo.png"
```

当前实现包含：

- 六通道 U-Net 基线模型
- SegFormer 六通道多标签头
- BCE/Focal + Dice 组合损失
- Macro Dice、Macro IoU、Precision/Recall、keypoint F1
- 单图推理输出原图尺寸 `[H,W,6]` 概率图和二值 mask

SegFormer 训练需要联网下载 Hugging Face 预训练权重，建议在云 GPU 环境运行。
