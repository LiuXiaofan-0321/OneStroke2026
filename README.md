# OneStroke2026 模型模块

coding：fy、zrh、lxf

本仓库是 2026 年“一笔成章”项目的独立模型工程。旧 OneStroke 仓库只作为数据、标签生成逻辑和 U-Net 权重来源参考，不继承旧训练框架。

## 当前阶段目标

7 月先完成数据、训练、评测和推理闭环：

- 审计旧数据目录，生成 `manifest.csv`
- 固定 `train/val/test` 划分，生成 `splits.csv`
- 固定六通道 schema：`vec1, vec2, vec3, vec4, vec5, keypoint`
- 重测 U-Net baseline
- 推进 SegFormer-B2 云端高精度主线
- 准备 SAM2 受控实验和笔画实例数据
- 为字体/书家风格选择功能预留 `target_style_id` 接口

## 重要设计文档

- [SAM2 + SegFormer-B2 + 字体风格选择 + 云端/端侧双模型完整训练路线](docs/font_aware_model_plan.md)
- [张荣昊阶段任务：数据问题复核 + U-Net 重测基线](docs/zhang_ronghao_task_1_3.md)
- [刘小凡任务二：困难样本集整理](docs/liuxiaofan_task_2_hardset.md)
- [SegFormer-B2 v1 上云训练前检查单](docs/segformer_v1_preflight.md)
- [U-Net 重测基线报告（v1）](docs/unet_rebaseline_report_2026-07-12.md)

## 推荐目录

```text
OneStroke2026/
  configs/              # 数据、训练、模型配置
  src/onestroke_model/  # Python 包源码
  docs/                 # 设计文档和任务文档
  artifacts/            # 生成的 manifest、split、报告、checkpoint（默认不提交）
```

## 安装

建议 Python 3.11。先从 GitHub 克隆仓库，再进入项目目录：

```powershell
git clone https://github.com/LiuXiaofan-0321/OneStroke2026.git
cd OneStroke2026
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[train]"
```

HTTP 模型服务联调还需要安装 `serve` 依赖，部署与接口文档见
[`docs/http_api_handoff.md`](docs/http_api_handoff.md)：

```powershell
python -m pip install -e ".[train,serve]"
```

如果只是先跑数据审计，基础依赖即可：

```powershell
python -m pip install -e .
```

## 1. 生成数据审计与 manifest

将 `--data-root` 指向旧仓库的 `StrokeSegmentation/data/output_img`：

```powershell
python -m onestroke_model.scripts.audit_data `
  --data-root "<LOCAL_ONESTROKE_PATH>\StrokeSegmentation\data\output_img" `
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
python eval.py --config ".\configs\train_unet.yaml" --checkpoint ".\artifacts\runs\unet_rebaseline\checkpoints\best.pt"
python infer.py --config ".\configs\train_segformer_b2.yaml" --checkpoint ".\artifacts\checkpoints\best.pt" --image ".\demo.png"
```

首次在新环境或云 GPU 上训练前，先运行只含一个训练 batch 和一个验证 batch 的集成检查：

```powershell
python train.py --config ".\configs\train_unet_smoke.yaml"
```

该检查会验证六通道数据加载、自动类别权重、边界损失、前向/反向传播、余弦调度、checkpoint 和验证指标链路；其输出位于 `artifacts/runs/unet_smoke/`，不应作为正式基线结果。

SegFormer-B2 的云端训练顺序、三组消融、增强人工检查和验证集阈值校准均以 [v1 上云训练前检查单](docs/segformer_v1_preflight.md) 为准。

当前实现包含：

- 六通道 U-Net 基线模型
- SegFormer 六通道多标签头
- BCE/Focal + Dice 组合损失
- Macro Dice、Macro IoU、Precision/Recall、keypoint F1
- 单图推理输出原图尺寸 `[H,W,6]` 概率图和二值 mask

SegFormer 训练需要联网下载 Hugging Face 预训练权重，建议在云 GPU 环境运行。

## IJDAR 投稿实验入口

当前研究管线围绕多标签笔画结构解析、受限参考对齐、结构一致性、
受控鲁棒性和局部诊断反馈建立。先运行统一预检：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m onestroke_model.scripts.run_ijdar_preflight `
  --project-root . `
  --output-dir artifacts/paper_ijdar/preflight
```

先从已取证的旧项目归档恢复并全量校验 840 个原始 GT 文件（该命令只恢复
原文件，不生成标签）：

```powershell
python -m onestroke_model.scripts.restore_legacy_gt `
  --archive "C:\path\to\OneStroke-main.tar.gz" `
  --destination data/legacy_gt_v1/output_img `
  --source-manifest artifacts/data_recovery/source_manifest_identity_v1.csv `
  --resolved-manifest artifacts/data_recovery/manifest_resolved.csv `
  --report artifacts/data_recovery/verification_report.json
```

恢复后必须建立冻结 QC 层。840 是“文件完整”数量，不是正式训练数量：

```powershell
python -m onestroke_model.scripts.build_dataset_qc
```

QC v1 排除 12 个原图/GT错配和 59 个完全重复非主实例，得到 769 个
QC-clean 独立样本。正式 Task 1 和 character-disjoint 实验只能使用
`artifacts/data_qc/` 下的固定 manifest、exclusion 和 split。

随后可生成不依赖 GPU 的冻结实验设计：

```powershell
python -m onestroke_model.scripts.build_character_disjoint_split `
  --manifest artifacts/data_audit/manifest.csv

python -m onestroke_model.scripts.run_character_disjoint_benchmark
python -m onestroke_model.scripts.run_controlled_perturbation_benchmark `
  --cache-index references/cache/segformer_b2_v1/index.json `
  --output-dir artifacts/paper_ijdar/controlled_perturbation
python -m onestroke_model.scripts.run_structure_score_audit `
  --cache-index references/cache/segformer_b2_v1/index.json `
  --output-dir artifacts/paper_ijdar/structure_score_audit
python -m onestroke_model.scripts.run_cross_reference_benchmark
python -m onestroke_model.scripts.run_alignment_ablation
python -m onestroke_model.scripts.run_feedback_diagnostic_benchmark `
  --cache-index references/cache/segformer_b2_v1/index.json `
  --output-dir artifacts/paper_ijdar/feedback_diagnostic
python -m onestroke_model.scripts.prepare_expert_study_templates
python -m onestroke_model.scripts.prepare_real_world_smartphone_templates
python -m onestroke_model.scripts.build_ijdar_paper_results
python -m onestroke_model.scripts.build_ijdar_paper_figures
```

`build_character_disjoint_split` 仅用于复现原始字符分配；正式训练使用在该字符
分配后应用 QC 的派生 split，不允许重新随机分字符。

正式 reference 实验只在
`references/cache/segformer_b2_v1/index.json` 通过 schema、provenance 和
artifact 校验后运行。缺少真实 cache 时脚本输出 `BLOCKED` 和
`run_manifest.json`，不会用 synthetic smoke 数字代替论文结果。

主要协议：

- [Controlled Perturbation Benchmark](docs/controlled_perturbation_benchmark.md)
- [Structure Score Audit](docs/structure_score_audit.md)
- [Alignment Ablation](docs/alignment_ablation.md)
- [Feedback Diagnostic Accuracy Benchmark](docs/feedback_diagnostic_accuracy_benchmark.md)
- [Feedback Diagnostic Rules v2](docs/feedback_diagnostic_fixes_v2.md)
- [Character-Disjoint Generalization](docs/character_disjoint_protocol.md)
- [Expert Study Ethics Checklist](docs/expert_study_ethics_checklist.md)
- [Smartphone / Unseen-Writer Protocol](docs/real_world_smartphone_protocol.md)
