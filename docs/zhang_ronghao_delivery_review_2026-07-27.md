# 张荣昊任务 1、3 交付复核（2026-07-27）

## 复核对象

压缩包：`zhang_ronghao_task_1_3_deliverables_20260712.tar.gz`

包含：

```text
artifacts/data_audit/bad_samples_review.csv
artifacts/runs/unet_rebaseline/checkpoints/best.pt
artifacts/runs/unet_rebaseline/val_metrics.json
artifacts/runs/unet_rebaseline/test_metrics.json
artifacts/runs/unet_rebaseline/notes.md
```

其中以 `._` 开头的条目是 macOS Finder 生成的资源叉文件，不是项目有效交付，可忽略。

## 任务 1：数据问题样本复核

**结论：完成。**

- 共确认 54 个无效样本，均来自 `char_id=40,41,42`。
- 每个目录 18 个样本，共 `3 x 18 = 54`。
- 六个标签通道均缺失，原图存在。
- 更关键的是，这三个目录包含的是不同书写者的姓名字符，不是“同一个字的多书写者样本”，不满足训练数据定义。
- 审核表中的决策均为 `drop`，判断正确。

当前工程的审计结果与此一致：894 个样本中 840 个完整可用，训练/验证/测试固定划分为 600/120/120。

## 任务 3：U-Net 重测基线

**结论：完成，且已进入主仓库。**

压缩包中的测试指标：

| 指标 | 结果 |
| --- | ---: |
| Macro Dice | 0.8913 |
| Macro IoU | 0.8049 |
| Keypoint F1 | 0.7531 |
| Boundary F1 | 0.7385 |

结果与当前仓库中记录的基线一致。相关代码、配置、报告和 Git LFS checkpoint 已在提交 `6d4d072` 与 `58abd75` 中进入主分支：

```text
configs/train_unet_rebaseline_v1.yaml
docs/unet_rebaseline_report_2026-07-12.md
checkpoints/unet_rebaseline_v1/best.pt
```

训练器的 CUDA 路径保持可用，并增加了 Apple Silicon MPS 回退支持。后续在云端运行 SegFormer-B2 不受该兼容性改动影响。

## 非阻塞缺口

交付压缩包没有再次包含完整的 `manifest.csv`、`splits.csv` 和数据审计报告；这不是阻塞问题，因为这些文件已在当前主工程的 `artifacts/data_audit/` 中存在。压缩包也未包含失败案例表和可视化预览，属于原任务说明中的可选项，不影响 U-Net 基线的可信性。

## 结论

张荣昊负责的任务 1、3 可正式标记为完成。后续无需重复训练 U-Net，应将精力转向参考字数据接入、评分链路和后续字体条件化。
