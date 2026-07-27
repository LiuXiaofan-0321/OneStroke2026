# 课程练习包模型交接（开发联调版）

日期：2026-07-27
模型版本：`segformer-b2-v1`
接口 schema：`1`

## 可交接能力

模型侧已交付两门有限字表课程。课程模式不依赖 OCR：前端从课程字格中传入
`course_id` 和 `target_char`，模型只允许使用当前课程中存在的同字参考。

| `course_id` | 前端展示名 | 已支持字符 | `style_id` |
| --- | --- | ---: | --- |
| `ouyang_xun_regular_100_beta` | 欧阳询楷书·100字练习包（Beta） | 100 | `ouyang_xun_regular_calli_tongji_beta` |
| `wang_xizhi_running_100_beta` | 王羲之行书·100字练习包（Beta） | 100 | `wang_xizhi_running_calli_tongji_beta` |

这两门课程来自 Calli-Tongji Beta 的已审核单字参考，许可证为 `CC-BY-NC-4.0`。
它们不是《兰亭序》或某个具体碑帖版本；前端不得改写课程来源表述。

## 部署前准备

以下文件不提交 GitHub，部署节点必须自行准备：

1. `checkpoints/segformer_b2_v1/best.pt`（Git LFS）；
2. Calli-Tongji Beta 原始 zip，按 `docs/calli_tongji_beta_reference_library.md` 导入；
3. `references/cache/segformer_b2_v1/index.json` 及对应的 `.npz` mask cache。

部署机的最小验证：

```bash
export PYTHONPATH="$PWD/src"

python -m onestroke_model.scripts.build_course_catalog \
  --course-config ./configs/course_packs.yaml \
  --output ./artifacts/course_packs/catalog.json \
  --require-cache
```

预期生成两个课程、各 100 个字符。`catalog.json` 是课程页字格和 `reference_id`
映射的唯一前端安全来源；前端不要扫描服务器目录，也不要硬编码字符列表。

## 一次练习分析

模型服务或业务后端调用：

```bash
python -m onestroke_model.scripts.analyze_course_practice \
  --image ./user_character.png \
  --course-id ouyang_xun_regular_100_beta \
  --target-char 亮 \
  --model-config ./configs/segformer_b2_v1_delivery.yaml \
  --checkpoint ./checkpoints/segformer_b2_v1/best.pt \
  --course-config ./configs/course_packs.yaml \
  --output-dir ./artifacts/practice/example_001
```

生产服务应在启动时创建一次 `CoursePracticeAnalyzer.from_paths(...)` 并复用实例，
不要每个请求重复加载 B2 checkpoint。

业务请求最小字段：

```json
{
  "practice_id": "practice_001",
  "course_id": "ouyang_xun_regular_100_beta",
  "target_char": "亮",
  "image": "PNG/JPEG file"
}
```

服务端从 `course_id` 决定 `style_id` 与参考图，不接受前端直接指定任意
`reference_id`，以免把错误字或错误课程混入评分。

## 输出资产

`--output-dir` 中会生成：

| 文件 | 用途 |
| --- | --- |
| `result.json` | 前端轮询完成后读取的汇总结果 |
| `prediction.npz` | 六通道概率图与二值 mask，供内部调试/复核 |
| `mask_vec1.png` … `mask_keypoint.png` | 六通道分割图 |
| `overlay.png` | 用户图上的六通道分割叠图与关键点 |
| `alignment_overlay.png` | 用户 mask 与课程同字参考的结构对齐叠图 |
| `evidence.json` | 原始、可审计的结构评分证据 |
| `feedback_contract.json` | 规则反馈、LLM 限制与可选 LLM prompt |
| `llm_feedback.json` | 仅在配置 LLM 后生成的自然语言反馈 |

`result.json` 的关键字段：

```json
{
  "schema_version": 1,
  "model_version": "segformer-b2-v1",
  "course": {
    "course_id": "ouyang_xun_regular_100_beta",
    "display_name": "欧阳询楷书·100字练习包（Beta）"
  },
  "reference": {
    "reference_id": "...",
    "target_char": "亮"
  },
  "capabilities": {
    "segmentation": true,
    "keypoint_localization": true,
    "stroke_region_extraction": true,
    "style_conditioning": true,
    "style_scoring": true,
    "natural_language_feedback": true,
    "stroke_order_analysis": false
  },
  "scores": {"prototype_structure_score": 0},
  "feedback": [],
  "overlay_asset": "overlay.png",
  "alignment_overlay_asset": "alignment_overlay.png"
}
```

## 评分语义与展示要求

`prototype_structure_score` 的展示名固定为“参考结构匹配度”。它由五个笔向
通道 Dice、整体墨迹 IoU 和关键点容忍 F1 加权得到，不是书法老师标定后的
审美分数，也不能写成“书法考试成绩”。

对齐仅允许平移、`0.80–1.20` 的等比缩放和 `+/-3` 度旋转；禁止非等比拉伸
和局部形变。前端应展示 `alignment_overlay.png`，让用户能看到反馈的依据。

`feedback` 是模型规则层生成的 Top-3 可执行问题。它可能包括整体重心、整体
大小、关键点关系和局部笔画结构；每条都带可追溯 evidence。不要只显示一个
总分而隐藏这些证据。

`stroke_regions` 是从五个笔向 mask 中提取的连通区域，包含 `region_id`、笔向
通道、外接框、面积和重心。前端可据此高亮局部笔画区域。它不是可靠恢复的书写
笔顺，因此必须保持 `stroke_order_analysis=false`，不能标成“第几笔”。

## LLM 建议接入

默认情况下，模型已返回确定性的中文建议，不会访问外部 API。若业务后端已
配置可信的 OpenAI 兼容接口，可增加：

```bash
export ONESTROKE_LLM_API_KEY='server-side-secret-only'

python -m onestroke_model.scripts.analyze_course_practice \
  ...同上参数... \
  --llm-url 'https://your-provider.example/v1/chat/completions' \
  --llm-model 'your-text-model'
```

密钥只能存在业务后端或模型服务环境变量，绝不能放入前端、课程 catalog、日志或
GitHub。LLM 只会获得 `feedback_contract.json` 中的结构化证据和受限 prompt；
它可以润色表达，但不得修改分数、虚构笔顺或宣称专家审美结论。

若 LLM 调用失败，业务后端应返回 `feedback_contract.json` 中的
`deterministic_feedback`，不能让整次 B2 分析失败。

## 错误处理

| 情况 | 建议业务错误码 | 前端行为 |
| --- | --- | --- |
| 未知/禁用课程 | `40002` | 回到课程页重新选择 |
| 课程没有该目标字 | `40901` | 显示“该课程暂未收录此字”，不生成伪评分 |
| 参考 cache 缺失 | `50301` | 保留练习记录，提示稍后重试 |
| 图片损坏或非 PNG/JPEG | `40001` | 提示重新导出或上传 |
| B2 推理或 LLM 调用失败 | `50001` | 保留练习记录并允许重试；LLM 失败时优先返回规则建议 |

## 当前边界

- 不做 OCR：课程练习已知目标字；任意图片识字属于后续功能。
- 不做可靠笔顺重建：当前是五笔向层加关键点分割，`stroke_order_analysis=false`。
- 不将 Beta 课程称为《兰亭序》或“欧阳询小楷”。
- 不把结构匹配度包装成经过专家校准的书法审美分数。
