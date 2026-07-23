# 对开发同学问题的答复（模型与数据接口）

日期：2026-07-23  
对应反馈文档：[OneStroke 项目当前开发反馈](https://my.feishu.cn/wiki/GWPvw1GfBirUq5kg3HVcjOtwnee)

> 本文是当前可执行的接口约定草案。需要特别区分：**已经实现的模型底层输出**、**正在训练/验证的能力**和**后续产品规划**。目前尚未部署可供网站调用的正式 HTTP 模型服务，开发侧可以先按本文的接口结构使用 Mock 数据联调。

## 一、先给结论

1. 当前模型不是 OCR，也不是直接生成评语的语言大模型。当前主线是 SegFormer-B2 视觉分割模型，把用户书写图像分成 `vec1–vec5 + keypoint` 六个独立通道。
2. 当前可以提供的底层结果是：六通道概率图、六张二值 mask、各通道阈值和推理耗时。HTTP 服务、评分规则、标注坐标转换和自然语言评语尚未正式交付。
3. 第一版网站应采用“点击保存练字后批改”，不做书写过程中的逐帧实时批改。前端提交后显示“AI 分析中”，通过任务 ID 查询结果。
4. 第一版模型最少需要用户书写后的 PNG/JPEG 图像。前端应直接上传 canvas 导出的图片文件，不建议只传一个任意公网 URL。
5. `target_char`、`target_style_id`、`reference_id` 应从第一版接口开始预留并传递；但当前分割 v1 不会真正依据字体风格打分。
6. 原始笔画轨迹不是当前分割模型的必需输入，但建议前端现在就保留采集能力。以后若要判断笔顺、运笔速度、停顿和起收笔过程，仅靠最终图片无法可靠恢复。

## 二、大模型能力边界

| 开发侧问题 | 当前回答 | 状态 |
| --- | --- | --- |
| 能否识别用户写了什么字 | 当前模型不承担 OCR。练习页面应把用户选择的目标字作为 `target_char` 传入 | 暂不支持自动识字 |
| 能否判断书写是否正确 | 当前模型只能分割方向区域和关键区域；要判断“是否正确”，还需和对应参考字对齐并建立规则/评分层 | 后续能力 |
| 能否评价结构、笔画、重心、收笔 | 重心、宽高比、轮廓、关键点偏移等可以基于分割结果与参考字做可解释几何比较；笔顺、运笔过程需轨迹数据 | 规划中，尚未交付 |
| 能否输出评分 | 当前没有经过书法专家标定的可靠评分。后续先输出结构、笔画形态、关键点位置等分项分数，不建议一开始做主观的 100 分制 | 规划中 |
| 能否生成老师评语 | 当前视觉模型不直接生成自然语言。可先由结构化问题标签套用专家审核过的评语模板，之后再考虑让语言模型润色 | 规划中 |
| 能否返回错误笔画坐标 | 模型能输出原图尺寸下的 mask；将 mask 转成框、轮廓或关键点坐标的适配层还需开发 | 可实现，尚未封装 |
| 是否支持字体选择 | 前端可以传字体风格 ID；当前 v1 仅保留字段，不做字体条件化评分 | 字段可接，模型能力后续实现 |

当前六通道固定顺序为：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

六通道使用独立 Sigmoid，交叉区域可以同时属于多个通道。前端不要假设它们是互斥分类，也不要自行调整通道顺序。

## 三、推荐的产品触发方式

第一版采用：

```text
用户完成书写
  → 点击“保存练字”
  → 保存练习记录与图片
  → 创建 AI 分析任务
  → 页面显示“AI 分析中”
  → 前端轮询任务状态
  → 展示 mask/标注/结构化反馈
```

暂时不做实时批改，原因是：

- 当前模型仍在定型，线上推理延迟和并发尚未实测；
- 分析需要完整汉字图像，书写中途结果会频繁变化；
- 保存后异步分析不会阻塞页面，也方便失败重试和记录模型版本；
- 共享训练集群不是正式在线推理服务器，不能承诺持续在线。

后续若实时推理条件成熟，可增加“停止书写 500–800 ms 后预览”的模式，但应保留任务取消与结果版本控制。

## 四、前端应该传什么

### 4.1 当前必需字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `image` | PNG/JPEG 文件 | 是 | canvas 使用 `toBlob` 导出；透明背景应先合成白底 |
| `practice_id` | string | 是 | 已保存的练习记录 ID，便于回写分析结果 |
| `target_char` | string | 是 | 用户当前临摹的目标汉字，例如“永” |
| `target_style_id` | string | 是 | 字体/书家代码；当前 v1 会保留但不参与评分 |
| `reference_id` | string | 否 | 具体参考字版本；有参考字比较能力后必填 |
| `canvas_width` | integer | 是 | 原 canvas 宽度 |
| `canvas_height` | integer | 是 | 原 canvas 高度 |

建议文件限制：PNG/JPEG，单张不超过 10 MB。前端可以上传原始尺寸，模型服务会等比例 padding/resize 到 `512×512`，并将结果恢复到原图尺寸。

### 4.2 建议现在就预留的轨迹字段

```json
{
  "strokes": [
    {
      "stroke_index": 0,
      "points": [
        {"x": 0.42, "y": 0.18, "t_ms": 0, "pressure": 0.58},
        {"x": 0.43, "y": 0.20, "t_ms": 16, "pressure": 0.61}
      ]
    }
  ]
}
```

- `x/y` 建议归一化到 `[0,1]`，避免依赖某个设备分辨率；
- `t_ms` 从本次书写开始计时；
- `pressure` 没有设备支持时可传 `null`；
- 当前 SegFormer v1 不读取这个字段，但未来判断笔顺、速度、停顿和运笔过程会用到。

课程 ID、课时 ID、用户 ID 等属于业务记录上下文，可由业务后端保存，不是分割模型的直接输入。

## 五、推荐的接口架构

浏览器不应直接访问 GPU 模型服务：

```text
浏览器/前端
  → OneStroke 业务后端（用户 JWT、练习记录、对象存储）
  → 内部模型服务（服务间鉴权）
  → 业务后端保存分析结果
  → 前端查询并展示
```

这样可以避免在浏览器中暴露模型服务器地址、内部 Token 和原始概率文件。

## 六、可供开发侧 Mock 的接口文档

### 6.1 创建书写分析任务

**接口名称：** 创建书写分析任务  
**接口描述：** 保存练习图片后创建异步 AI 分析任务  
**请求方式：** `POST`  
**请求 URL：** `/api/v1/practice-evaluations`  
**是否需要鉴权：** 是，沿用网站用户 JWT/Session  
**Content-Type：** `multipart/form-data`

请求参数：

| 参数名 | 类型 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `image` | file | 是 | PNG/JPEG 书写图像 |
| `practice_id` | string | 是 | 练习记录 ID |
| `target_char` | string | 是 | 目标汉字 |
| `target_style_id` | string | 是 | 目标字体风格代码 |
| `reference_id` | string | 否 | 参考字资源版本 |
| `canvas_width` | integer | 是 | canvas 原始宽度 |
| `canvas_height` | integer | 是 | canvas 原始高度 |
| `strokes_json` | JSON string | 否 | 原始笔画轨迹 |

示例响应（HTTP `202 Accepted`）：

```json
{
  "code": 0,
  "message": "accepted",
  "data": {
    "task_id": "eval_20260723_000001",
    "practice_id": "practice_123",
    "status": "queued",
    "poll_after_ms": 1000
  }
}
```

### 6.2 查询书写分析结果

**接口名称：** 查询书写分析任务  
**请求方式：** `GET`  
**请求 URL：** `/api/v1/practice-evaluations/{task_id}`  
**是否需要鉴权：** 是

任务状态：

```text
queued | running | succeeded | failed
```

当前 schema v1 成功响应建议：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "eval_20260723_000001",
    "practice_id": "practice_123",
    "status": "succeeded",
    "schema_version": 1,
    "model_version": "segformer-b2-v1",
    "target_char": "永",
    "target_style_id": "zhao_mengfu_kaishu",
    "capabilities": {
      "segmentation": true,
      "style_scoring": false,
      "natural_language_feedback": false,
      "stroke_order_analysis": false
    },
    "result": {
      "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
      "thresholds": {
        "vec1": 0.5,
        "vec2": 0.5,
        "vec3": 0.5,
        "vec4": 0.5,
        "vec5": 0.5,
        "keypoint": 0.45
      },
      "mask_assets": {
        "vec1": "/assets/evaluations/eval_20260723_000001/vec1.png",
        "vec2": "/assets/evaluations/eval_20260723_000001/vec2.png",
        "vec3": "/assets/evaluations/eval_20260723_000001/vec3.png",
        "vec4": "/assets/evaluations/eval_20260723_000001/vec4.png",
        "vec5": "/assets/evaluations/eval_20260723_000001/vec5.png",
        "keypoint": "/assets/evaluations/eval_20260723_000001/keypoint.png"
      },
      "overlay_url": "/assets/evaluations/eval_20260723_000001/overlay.png",
      "annotations": [],
      "scores": null,
      "feedback": []
    },
    "latency_ms": 0
  }
}
```

说明：模型内部可以产生 `[H,W,6]` 浮点概率图，但不建议把整块浮点数组直接塞进面向浏览器的 JSON。业务后端可以保存为压缩文件；前端优先接收 mask/overlay 资源 URL、RLE 或经过筛选的坐标标注。

后续 schema v2 才增加：

```json
{
  "scores": {
    "global": 0.82,
    "structure": 0.78,
    "stroke_shape": 0.85,
    "keypoint_position": 0.80
  },
  "feedback": [
    {
      "type": "center_shift",
      "severity": "medium",
      "message": "整体重心略偏右",
      "annotation_ids": ["ann_001"]
    }
  ]
}
```

开发侧应根据 `schema_version` 和 `capabilities` 决定显示内容，不要看到字段存在就默认该能力已经开放。

### 6.3 错误码建议

| 错误码 | 含义 | 处理建议 |
| --- | --- | --- |
| `40001` | 图片为空、损坏或格式不支持 | 提示用户重新书写/上传 |
| `40002` | 缺少目标字或字体风格 | 检查页面上下文 |
| `40401` | 任务不存在或不属于当前用户 | 停止轮询并刷新记录 |
| `40901` | 对应参考字/风格资源尚未准备 | 回退到基础分割展示 |
| `42901` | 请求过于频繁 | 按 `retry_after_ms` 重试 |
| `50001` | 模型推理失败 | 保留练习记录，允许重新分析 |
| `50301` | 模型服务暂不可用 | 页面显示稍后重试，不丢失作品 |

## 七、字体选择如何接入

前端现在就传稳定的机器代码，不要只传中文展示名称。例如：

```json
{
  "target_style_id": "zhao_mengfu_kaishu",
  "target_style_name": "赵孟頫楷体"
}
```

字体字典由业务后端维护；模型接口只依赖 `target_style_id`。当前 v1 会原样记录/回传，但不会依据该 ID 改变分割或输出风格分数。字体条件化模型和参考字几何评分在分割主线稳定后开发。

## 八、数据问题的回答

### 8.1 视频与课程资源

这一项不能由模型组单独决定，需要项目负责人、课程内容负责人和书法专业成员确认。建议来源优先级：

1. 团队自行录制并拥有版权的课程；
2. 学校/指导教师明确授权的资料；
3. 正式采购或取得书面授权的资源；
4. 开源或公版资源，但必须保留许可和来源记录。

不建议直接抓取网络课程或书法作品用于公开产品，版权风险需要单独评估。开发阶段可继续使用明确标注为 Mock 的占位数据。

### 8.2 每个字的笔法要点、结构分析和练习提示

由书法专业成员/指导教师提供并审核，模型组可以提供结构化数据格式。建议每条参考资源至少包含：

```text
reference_id
target_char
style_id
reference_image
structure_tips
stroke_tips
common_errors
reviewer
review_status
source_and_license
version
```

模型生成的反馈必须以这些经过审核的内容为依据，不能把未经审核的自动文本直接标成“老师评语”。

### 8.3 评论、问答和社区帖子

这是业务/运营数据，不是模型训练数据。内测阶段可准备少量明确标记的种子内容；上线后主要来自真实用户，并配套举报、审核和删除机制。

## 九、域名问题

建议在需要团队远程联调、指导教师验收和答辩演示前部署域名及 HTTPS。内部早期联调可以暂用开发环境地址，因此购买域名不阻塞模型训练。

30 元经费是否批准属于负责人/财务决策。若购买，建议：

- 使用团队或项目可持续管理的账号，不绑定某位临时开发成员；
- 同时配置 HTTPS；
- 区分开发、测试和正式环境；
- 域名、云服务和续费信息记录到项目资产清单。

## 十、双方下一步分工

开发同学现在可以做：

- canvas 使用 `toBlob('image/png')` 导出白底图片；
- 保存 `target_char`、`target_style_id`、`reference_id`；
- 预留轨迹采集与 `strokes_json`；
- 按异步任务接口使用 Mock 数据联调；
- 页面根据 `status`、`schema_version`、`capabilities` 渲染；
- 支持分析失败后重试，且不能因模型失败丢失练习记录。

模型组需要交付：

- 定型后的 SegFormer-B2 checkpoint 和固定阈值；
- 单图推理服务与模型版本信息；
- mask/overlay/坐标适配层；
- 真实延迟、并发、超时和失败率测试；
- 参考字几何比较与评分规则；
- 经书法成员审核的反馈标签和评语模板。

目前开发侧最重要的认知是：**接口可以先接，AI 批改能力需要分阶段开放。第一阶段是可靠分割，不应把尚未完成的结构评分、字体评分和自然语言评语包装成已上线能力。**
