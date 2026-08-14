# Task 1 正式实验结果与归档说明

日期：2026-08-14

## 1. 完成状态

Task 1 的正式分割基准实验已经全部完成：

- 3 种模型：U-Net、DeepLabV3+、SegFormer-B2；
- 2 种数据划分：QC-clean standard split、QC-clean character-disjoint split；
- 3 个固定随机种子：`20260811`、`314159`、`271828`；
- 共 `3 × 2 × 3 = 18` 个正式训练与测试任务；
- 正式批处理退出码为 `0`；
- 18 个任务均标记为完成；
- 未发现 OOM、Traceback 或 RuntimeError。

本次训练使用的是经过 QC 排除后的真实六通道 GT 数据。200 个
SegFormer reference cache 不属于 GT，也未用于替代训练标签。

## 2. 三随机种子正式结果

数值均为三次独立运行的均值 ± 样本标准差。

### 2.1 QC-clean standard split

| 模型 | Macro Dice | Macro IoU | Keypoint F1 | Boundary F1 |
|---|---:|---:|---:|---:|
| U-Net | 0.919604 ± 0.001779 | 0.851492 ± 0.003020 | **0.756184 ± 0.003817** | 0.800921 ± 0.002263 |
| DeepLabV3+ | **0.963018 ± 0.000634** | **0.928713 ± 0.001192** | 0.721759 ± 0.001152 | **0.844331 ± 0.002793** |
| SegFormer-B2 | 0.958091 ± 0.003108 | 0.919588 ± 0.005718 | 0.713916 ± 0.004602 | 0.825909 ± 0.008781 |

### 2.2 QC-clean character-disjoint split

| 模型 | Macro Dice | Macro IoU | Keypoint F1 | Boundary F1 |
|---|---:|---:|---:|---:|
| U-Net | 0.826002 ± 0.016109 | 0.712008 ± 0.022495 | **0.697241 ± 0.004526** | 0.643003 ± 0.013565 |
| DeepLabV3+ | 0.866377 ± 0.009374 | 0.766277 ± 0.014566 | 0.675471 ± 0.003122 | 0.672767 ± 0.013847 |
| SegFormer-B2 | **0.886596 ± 0.000783** | **0.797659 ± 0.001297** | 0.660430 ± 0.003325 | **0.685090 ± 0.004576** |

### 2.3 Character-disjoint 性能下降

从 standard split 到 character-disjoint split，Macro Dice 的绝对下降为：

| 模型 | 下降（百分点） |
|---|---:|
| U-Net | 9.360 |
| DeepLabV3+ | 9.664 |
| SegFormer-B2 | 7.150 |

## 3. 可以写入论文的结论

1. 在 standard split 上，DeepLabV3+ 的方向分割、IoU 和边界指标最高。
2. 在 character-disjoint split 上，SegFormer-B2 的 Macro Dice、Macro IoU
   和 Boundary F1 最高，并且从 standard split 到 character-disjoint split
   的下降最小。
3. U-Net 在两种划分上的 strict Keypoint F1 均最高。
4. 结果不支持“某一个架构在所有指标上全面占优”的表述。
5. Character-disjoint 只验证未见汉字身份的迁移能力，不能等价表述为
   unseen-writer，也不能代替真实手机拍摄或新书写者测试。

## 4. 归档内容

Git 仓库中保存轻量、可审计的正式结果：

- `artifacts/paper_ijdar/task1/execution_plan.json`
- `artifacts/paper_ijdar/task1/results_per_seed.csv`
- `artifacts/paper_ijdar/task1/results_summary.csv`
- `artifacts/paper_ijdar/task1/summary_manifest.json`
- `artifacts/paper_ijdar/task1/checkpoint_manifest.csv`
- `artifacts/paper_ijdar/task1/formal_audit_manifest.json`
- `artifacts/paper_ijdar/task1/formal_run_file_manifest.csv`
- `artifacts/paper_ijdar/task1/formal_runs/`

`formal_runs/` 含 18 个实验目录，每个目录保存 8 个轻量文件：

- `benchmark_state.json`
- `test_metrics.json`
- `thresholds_val.json`
- `run_metadata.json`
- `final_metrics.json`
- `data_statistics.json`
- `metrics_history.json`
- `benchmark.log`

## 5. 完整性验证

正式审计结果：

```text
formal_exit_code = 0
expected_run_count = 18
verified_run_count = 18
all_checkpoints_present = true
all_hashes_verified = true
all_runs_completed = true
```

关键文件 SHA-256：

```text
results_per_seed.csv
c6d27f365fab15b71914c6ae1ccaf723b02e236c28dc2b4a656ad7c50ea7934e

results_summary.csv
dcd2fa5248d8a1a0fa5143fbe72dd75ae3269551b8e58d071e1d0f638b6d1d6c

summary_manifest.json
5bdd12f2b07d770ff846a88a3e8a02faf7ee9491555b0dea65c5fb329721601f

checkpoint_manifest.csv
f49c4fc8b364abe62eade730dc6f9b14e35d6baf809d5d7e5e6fb3d7462b391e
```

正式训练所依据的代码提交：

```text
56ade12b4dab49f26a35db09b7d59808da8fac3c
```

## 6. Checkpoint 保留策略

18 个正式实验 checkpoint 体积较大，不上传 GitHub。Git 仓库只保存：

- 每个 checkpoint 的路径、大小和 SHA-256；
- 每次运行的配置、日志、阈值和最终指标；
- 汇总表与完整性审计结果。

checkpoint 实体继续保存在 AutoDL 数据盘：

```text
/root/autodl-tmp/lxf/OneStroke2026
```

如需长期留档，应另行复制到对象存储、网盘或实验室存储空间；仅依赖
AutoDL 数据盘存在数据丢失风险。

## 7. 后续优先级

Task 1 不再继续调参。下一项论文优先工作应为：

1. 真实 smartphone 测试；
2. 真实 unseen-writer 测试；
3. 将上述结果填入论文当前保留的 `SMARTPHONE` 占位部分。
