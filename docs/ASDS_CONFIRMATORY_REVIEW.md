# ASDS 独立确认集内部审核说明

状态：`CANDIDATE_ONLY_DO_NOT_RATE`

在任何真人评分开始前，项目负责人需要先审核本地文件夹：

```text
artifacts/paper_ijdar/expert_validation/
  spatial_score_confirmatory_candidates_v1/
```

重点查看五张图：

```text
confirmatory_review_01.png
confirmatory_review_02.png
confirmatory_review_03.png
confirmatory_review_04.png
confirmatory_review_05.png
```

并填写：

```text
confirmatory_review_form.csv
```

只允许依据下列项目判断：

- `same_instance_suspected`
- `bad_image_suspected`
- `accidental_duplicate_suspected`
- `keep_for_freeze`
- `review_notes`

审核时禁止查看或计算：

- production score
- coverage-aware score
- ASDS
- 原 150 对人工评分
- 任何可能暗示模型高低分的排序

## 冻结规则

1. 100 对候选与原 150 对的 pair overlap 必须为 0。
2. 100 对候选与原 150 对的 glyph instance overlap 必须为 0。
3. 同一 pair 中不能是同一实例、同一图像或精确重复 mask。
4. 需要替换时，只能按照
   `confirmatory_reserve_pairs.csv` 中预先生成的顺序取下一项。
5. 所有替换完成后生成并记录最终 CSV 的 SHA-256。
6. 文件名改为 `frozen_confirmatory_pairs_v1.csv`。
7. 在第一位评价者开始评分以后，禁止修改 pair、图片、显示顺序、
   ASDS 特征、bin、权重、alignment、排除规则或主终点。

## 评分建议

- 继续使用 1--5 分“同字结构相似度”。
- 与原研究保持一致的盲化说明和界面。
- 最少 3 人；若能增加 2 名有稳定书法学习/教学背景的评价者更有力。
- 评分者不得接触模型分数、来源实例 ID 或开发集结果。
- 仍需加入隐藏重复题，用于评价者内部一致性。

只有该冻结确认集得到的新 Spearman rho，才能作为 ASDS 的独立确认
结果写入论文摘要和结论。
