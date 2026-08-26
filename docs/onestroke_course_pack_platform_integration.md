# OneStroke 两个书法练习包的平台接入说明

面向：`onestroke.cn` 前端、Java 业务后端和产品开发同学

课程配置版本：`schema_version = 1`

模型版本：`segformer-b2-v1`

## 1. 先用一句话说明“书法包”是什么

书法包不是给现有评分接口增加一个“字体名称”参数，也不是让同一个用户作品随意
和不同字体比较。

一个书法练习包是一个受限、可复现的课程单元：

```text
课程元数据
+ 固定的 100 字字表
+ 每个字唯一的同字参考
+ 预生成的参考六通道 mask
+ 用户对该字的书写任务
+ 同课程、同字的结构比较
+ 分割结果、匹配度、问题证据和 AI 建议
```

用户选择“欧阳询楷书·100字练习包（Beta）”中的“永”后，平台必须将用户写的
“永”与该课程中的欧阳询风格“永”参考比较。不能拿“永”去和“亮”比较，也不能
让前端自行指定任意 `reference_id`。

模型侧已经完成课程包选择、六通道分割、同字参考匹配、限制性对齐、结构评分和
反馈生成。平台开发需要增加的是课程页面、业务数据和接口转发，不需要重新训练模型。

## 2. 当前已经支持的两个课程

| `course_id` | 平台展示名称 | 字数 | `style_id` |
| --- | --- | ---: | --- |
| `ouyang_xun_regular_100_beta` | 欧阳询楷书·100字练习包（Beta） | 100 | `ouyang_xun_regular_calli_tongji_beta` |
| `wang_xizhi_running_100_beta` | 王羲之行书·100字练习包（Beta） | 100 | `wang_xizhi_running_calli_tongji_beta` |

参考数据来自 Calli-Tongji Beta，许可证为 `CC-BY-NC-4.0`。

平台展示时必须遵守以下口径：

- 保留课程名称中的“100字练习包（Beta）”；
- 标明参考来源为 Calli-Tongji Beta；
- 当前数据不能宣传为《兰亭序》《九成宫》、欧阳询小楷或某个具体碑帖；
- 若 `onestroke.cn` 用于商业用途，需要重新核对或取得商业授权；
- 分数展示名固定为“参考结构匹配度”；
- 不能称为“专家审美分”“考试成绩”或“书法水平等级”。

课程的唯一机器标识是 `course_id`。中文展示名以后可以调整，但数据库、前后端接口
和模型调用不能只依赖中文名称。

## 3. 它和平台原有“字体选择”有什么区别

如果现有平台只有一个“选择字体”的下拉框，然后仍允许用户练任意汉字，这还没有
真正接入书法包。

正确关系是：

```text
选择课程
  └── 决定允许练习的 100 个字
        └── 选择目标字
              └── 展示该课程的同字参考
                    └── 用户书写
                          └── course_id + target_char + image 一起提交
```

建议将平台功能分成两种模式：

1. **课程练习**
   - 只能选择该课程目录中的字；
   - 可以进行同字参考评分和课程反馈；
   - 本文档描述的两个书法包属于此模式。
2. **自由书写**
   - 可以写任意字；
   - 只做分割或保存作品；
   - 如果没有同字课程参考，不得生成伪造的书体匹配分。

切换课程时，前端必须重新检查当前 `target_char` 是否在新课程中。两个课程的字表
不应被假定为完全相同。

## 4. 推荐的平台结构

```text
浏览器前端（onestroke.cn）
        │
        │ 用户登录、课程选择、练习画布、结果展示
        ▼
OneStroke Java 业务后端
        │
        ├── 课程目录缓存
        ├── 用户与练习记录
        ├── 模型任务状态
        ├── 结果 JSON
        └── 图片资产保存或代理
        │
        │ 服务间 API Key
        ▼
Python 模型 HTTP 服务
        │
        ├── SegFormer-B2 六通道分割
        ├── 课程内同字参考选择
        ├── 限制性结构对齐
        ├── 参考结构匹配度
        └── 规则建议 / 可选 LLM 润色
```

浏览器不得直接请求模型服务，原因如下：

- 会暴露模型服务地址和服务密钥；
- AutoDL 地址可能变化或停止；
- 模型生成的图片接口也需要服务间鉴权；
- 练习记录、用户权限、失败重试和历史结果都属于 Java 后端职责；
- 模型服务关闭后，历史结果仍应能在 `onestroke.cn` 查看。

## 5. 平台页面应该如何增加

下面的路由是推荐信息架构，实际 URL 可以按现有前端工程调整。

### 5.1 课程列表页

示例路由：

```text
/courses
```

每个课程卡片至少显示：

- 课程展示名；
- 书家与书体；
- “100字”；
- Beta 标识；
- 来源说明；
- “进入课程”按钮；
- 用户已练字数、最近练习时间等进度信息（可后做）。

首版至少放两张卡片：

```text
欧阳询楷书·100字练习包（Beta）
王羲之行书·100字练习包（Beta）
```

### 5.2 课程详情与字表页

示例路由：

```text
/courses/{courseId}
```

页面从业务后端读取该课程的 100 字目录，以字格形式显示。每个字格至少包含：

- `target_char`；
- 是否练过；
- 最近一次参考结构匹配度；
- “开始练习”入口。

字表必须来自模型服务的 `/course-catalog` 同步结果，不能由前端手工写死。

### 5.3 单字练习页

示例路由：

```text
/courses/{courseId}/practice/{targetChar}
```

页面应包含：

- 课程名称；
- 当前目标字；
- 参考字展示图；
- 用户书写画布；
- 清空、撤销、重新书写和提交按钮；
- “提交后将进行参考结构分析”的说明。

课程模式不需要 OCR。因为用户从课程字表进入练习页，平台已经知道他正在写什么字，
应直接把路由中的 `targetChar` 作为 `target_char` 提交。

画布导出要求：

- 输出单个完整汉字的 PNG 或 JPEG；
- 白色背景、深色字迹；
- 透明画布应先合成到白色背景；
- 不要把米字格、参考字描红层、选中框、光标或按钮截进图片；
- 可以保留原始画布尺寸，模型会等比例填充到 `512×512`；
- 单张图片不超过 10 MB。

### 5.4 结果页

示例路由：

```text
/practice/{practiceId}/result
```

建议按以下顺序展示：

1. 参考结构匹配度；
2. 一句分数解释；
3. Top-3 可执行建议；
4. 用户字六通道叠图 `overlay`；
5. 用户与课程参考的对齐比较图 `alignment_overlay`；
6. 五个方向通道和关键点 mask；
7. 可点击的方向连通区域；
8. 课程、目标字、参考版本和模型版本。

结果页必须保留以下说明：

> 本结果反映用户书写与当前课程同字参考的结构匹配情况，不等同于书法考试成绩或
> 专家审美评级。

## 6. 课程目录如何同步

模型服务已经提供：

```http
GET /course-catalog
Authorization: Bearer <MODEL_SERVICE_KEY>
```

典型响应结构：

```json
{
  "schema_version": 1,
  "courses": [
    {
      "course_id": "ouyang_xun_regular_100_beta",
      "display_name": "欧阳询楷书·100字练习包（Beta）",
      "style_id": "ouyang_xun_regular_calli_tongji_beta",
      "source_dataset": "Calli-Tongji Beta",
      "source_license": "CC-BY-NC-4.0",
      "status": "beta_reference_pack",
      "enabled": true,
      "scoring_label": "参考结构匹配度",
      "supported_character_count": 100,
      "cache_available": true,
      "characters": [
        {
          "target_char": "永",
          "reference_id": "..."
        }
      ]
    }
  ]
}
```

推荐同步方式：

1. Java 后端启动后调用一次 `/course-catalog`；
2. 校验 `schema_version`、`enabled`、字符数和 `cache_available`；
3. 将课程和字表保存为本地数据库快照；
4. 前端只调用 Java 后端课程接口；
5. 每次模型服务部署后重新同步；
6. 模型服务短时不可用时，可以读取最后一次成功快照，但不能提交新的模型分析；
7. 如果某课程变为禁用状态，平台停止创建新练习，历史记录仍保留。

不要在每次打开课程页面时都让浏览器或 Java 后端实时请求 GPU 节点。

## 7. 建议的业务数据库

不要求完全使用下列名称，但数据关系必须保留。

### 7.1 `calligraphy_course`

| 字段 | 说明 |
| --- | --- |
| `course_id` | 主键，与模型配置完全一致 |
| `display_name` | 中文展示名 |
| `style_id` | 模型参考风格 ID |
| `source_dataset` | 参考数据来源 |
| `source_license` | 许可证 |
| `course_status` | Beta、禁用等状态 |
| `enabled` | 是否允许新建练习 |
| `scoring_label` | “参考结构匹配度” |
| `schema_version` | 目录 schema |
| `catalog_synced_at` | 最近同步时间 |

### 7.2 `course_character`

| 字段 | 说明 |
| --- | --- |
| `course_id` | 所属课程 |
| `target_char` | 单个 Unicode 汉字 |
| `reference_id` | 当前批准的参考版本 |
| `display_order` | 字格顺序 |
| `enabled` | 是否开放练习 |
| `reference_asset_url` | 平台保存的参考字展示图，可为空 |

建议对 `(course_id, target_char)` 建立唯一约束。

### 7.3 `practice_record`

| 字段 | 说明 |
| --- | --- |
| `practice_id` | 平台练习记录 ID |
| `user_id` | 用户 ID |
| `course_id` | 课程 ID |
| `target_char` | 目标字 |
| `input_image_url` | 用户原始书写图 |
| `analysis_status` | `pending/running/succeeded/failed` |
| `created_at` | 创建时间 |
| `completed_at` | 完成时间 |

### 7.4 `practice_analysis`

| 字段 | 说明 |
| --- | --- |
| `practice_id` | 对应练习 |
| `model_task_id` | 模型返回的 `task_id` |
| `model_version` | 如 `segformer-b2-v1` |
| `reference_id` | 本次实际使用的同字参考 |
| `score` | `prototype_structure_score` |
| `score_label` | “参考结构匹配度” |
| `feedback_json` | 规则反馈 |
| `ai_feedback_json` | 可选 LLM 润色结果 |
| `segmentation_json` | 通道、阈值、关键点和区域 |
| `overlay_asset_url` | 已持久化的平台图片地址 |
| `alignment_asset_url` | 已持久化的平台图片地址 |
| `mask_assets_json` | 六通道图片地址 |
| `raw_result_json` | 原始响应，便于复核 |

必须保存 `course_id + target_char + reference_id + model_version`，否则以后课程或模型更新后，
无法说明一条历史分数是怎样产生的。

## 8. 建议提供给前端的 Java 业务接口

以下接口属于 `onestroke.cn` 业务后端，不是模型服务原始接口。

### 8.1 获取课程列表

```http
GET /api/calligraphy/courses
```

只返回当前启用课程、课程简介和用户进度。

### 8.2 获取课程详情和字表

```http
GET /api/calligraphy/courses/{courseId}
```

返回：

```json
{
  "course_id": "ouyang_xun_regular_100_beta",
  "display_name": "欧阳询楷书·100字练习包（Beta）",
  "scoring_label": "参考结构匹配度",
  "supported_character_count": 100,
  "characters": [
    {
      "target_char": "永",
      "reference_image_url": "/api/calligraphy/courses/ouyang_xun_regular_100_beta/references/永",
      "practiced": false,
      "latest_score": null
    }
  ]
}
```

### 8.3 创建一次练习分析

```http
POST /api/calligraphy/practices
Content-Type: multipart/form-data
Authorization: <用户登录凭证>
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `image` | 是 | 用户画布导出的单字图片 |
| `course_id` | 是 | 当前课程 |
| `target_char` | 是 | 当前课程中的目标字 |

推荐先返回：

```json
{
  "practice_id": "practice_001",
  "status": "pending"
}
```

Java 后端异步调用模型服务。这样不会因为 GPU 推理或 LLM 响应时间阻塞浏览器请求。
如果现阶段用户量很小，也可以先同步调用，但数据库仍应保留任务状态。

### 8.4 查询练习结果

```http
GET /api/calligraphy/practices/{practiceId}
```

前端可以轮询，直到：

```json
{
  "practice_id": "practice_001",
  "status": "succeeded",
  "course": {},
  "reference": {},
  "scores": {},
  "feedback": [],
  "ai_feedback": {},
  "segmentation": {},
  "overlay_url": "/api/calligraphy/practices/practice_001/assets/overlay",
  "alignment_overlay_url": "/api/calligraphy/practices/practice_001/assets/alignment"
}
```

### 8.5 读取结果图片

```http
GET /api/calligraphy/practices/{practiceId}/assets/{assetType}
```

`assetType` 可包括：

```text
overlay
alignment
mask-vec1
mask-vec2
mask-vec3
mask-vec4
mask-vec5
mask-keypoint
```

业务后端必须检查当前用户是否有权查看该练习，不能把模型服务密钥返回给浏览器。

## 9. Java 后端如何调用模型服务

模型服务分析接口：

```http
POST /analyze-course-practice
Content-Type: multipart/form-data
Authorization: Bearer <MODEL_SERVICE_KEY>
```

四个字段必须同时存在：

```text
image
practice_id
course_id
target_char
```

示例：

```bash
curl -X POST 'MODEL_BASE_URL/analyze-course-practice' \
  -H 'Authorization: Bearer MODEL_SERVICE_KEY' \
  -F 'image=@user_character.png;type=image/png' \
  -F 'practice_id=practice_001' \
  -F 'course_id=ouyang_xun_regular_100_beta' \
  -F 'target_char=永'
```

重要规则：

- `MODEL_SERVICE_KEY` 只存在 Java 后端服务器环境变量或密钥管理系统；
- 前端不能传 `reference_id`；
- Java 后端先验证 `course_id + target_char` 是否存在于本地课程快照；
- 模型服务会再次验证，双重校验不是重复工作；
- 不要把 `style_id` 代替 `course_id` 提交；
- 不要调用 OCR 猜测 `target_char`；
- 同一 `practice_id` 的重复请求应由业务后端做幂等或生成新的分析版本。

## 10. 模型成功响应如何使用

模型响应的核心结构如下：

```json
{
  "task_id": "eval_...",
  "practice_id": "practice_001",
  "status": "succeeded",
  "schema_version": 1,
  "model_version": "segformer-b2-v1",
  "course": {
    "course_id": "ouyang_xun_regular_100_beta",
    "display_name": "欧阳询楷书·100字练习包（Beta）",
    "style_id": "ouyang_xun_regular_calli_tongji_beta",
    "status": "beta_reference_pack"
  },
  "reference": {
    "reference_id": "...",
    "target_char": "永"
  },
  "scores": {
    "prototype_structure_score": 82.0
  },
  "feedback": [
    {
      "type": "structure",
      "severity": "medium",
      "message": "...",
      "action": "..."
    }
  ],
  "ai_feedback": {
    "source": "llm"
  },
  "segmentation": {
    "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
    "thresholds": {},
    "latency_ms": 0,
    "keypoints": [],
    "stroke_regions": [],
    "mask_urls": {
      "vec1": "MODEL_BASE_URL/artifacts/eval_.../mask_vec1.png"
    }
  },
  "overlay_url": "MODEL_BASE_URL/artifacts/eval_.../overlay.png",
  "alignment_overlay_url": "MODEL_BASE_URL/artifacts/eval_.../alignment_overlay.png",
  "score_interpretation": "..."
}
```

Java 后端收到响应后应立即：

1. 校验 `practice_id`、`course.course_id` 和 `reference.target_char`；
2. 保存完整原始 JSON；
3. 保存 `model_version` 和 `reference_id`；
4. 使用服务密钥下载 `overlay_url`、`alignment_overlay_url` 和六张 `mask_urls`；
5. 将图片保存到平台对象存储或业务服务器；
6. 将数据库中的模型临时 URL 替换为平台长期 URL；
7. 更新练习状态为 `succeeded`；
8. 再允许前端读取结果。

不要只把 AutoDL 返回的图片 URL 原样存进数据库。AutoDL 关机、换实例或清理
`artifacts` 后，这些链接会失效。

## 11. 六通道分割在页面中怎么展示

固定通道顺序是：

```text
vec1, vec2, vec3, vec4, vec5, keypoint
```

五个 `vec` 通道是允许重叠的方向区域，`keypoint` 是独立关键区域。同一个交叉位置
可以同时出现在多个方向通道中，因此前端不能把它们当作互斥的语义分割类别。

`stroke_regions` 中的每一项包含：

```json
{
  "region_id": "vec1_001",
  "channel": "vec1",
  "area": 123,
  "centroid": {"x": 100.0, "y": 120.0},
  "bbox": {
    "left": 80,
    "top": 100,
    "right": 130,
    "bottom": 150
  }
}
```

前端可以：

- 点击某个方向通道，只显示对应 mask；
- 根据 `bbox` 在原图上高亮区域；
- 点击一条建议时，高亮它关联的区域；
- 用 `overlay` 作为默认总览；
- 单独显示 `keypoint`。

前端不能：

- 将 `region_id` 显示为“第 1 笔、第 2 笔”；
- 根据区域位置猜测笔顺；
- 将一个连通区域承诺为一条完整真实笔画；
- 自行改变六通道顺序；
- 在未核对真实标签协议前，擅自把 `vec1–vec5` 固定翻译成具体笔画名。

目前 `stroke_regions` 是方向连通区域，不是时间顺序上的单笔实例。页面可以写
“方向区域”或“笔画结构区域”，不能写“笔顺分析”。

如果产品需要显示“横向、竖向、左斜、右斜、点状/短笔”等中文标签，模型组和开发组
应先共同冻结一份版本化 `channel_schema`，明确每个 `vec` 的真实标签定义，再由前端
按 schema 映射。不能只凭颜色或视觉感觉猜映射。

## 12. AI 建议怎么展示

`feedback` 是模型结构证据生成的确定性建议；`ai_feedback` 是可选文本大模型对这些
证据的语言组织。

判断方式：

```text
ai_feedback.source = "llm"
    表示 LLM 润色成功

ai_feedback.source = "deterministic"
    表示未配置 LLM 或 LLM 失败，已回退到规则建议
```

无论是否使用 LLM，结构分割和参考结构匹配度都仍然有效。

前端建议：

- 总是显示 `feedback` 中可审计的结构建议；
- LLM 成功时，可将 `ai_feedback` 作为更自然的总结；
- LLM 失败时不把整次分析标成失败；
- 不允许 LLM 修改模型分数；
- 不显示模型没有证据支持的笔顺、运笔速度或书法家审美结论。

## 13. 参考字展示图的当前缺口

`GET /course-catalog` 出于服务器路径安全考虑，不会返回本地
`reference_image_path`。当前模型 HTTP 服务也没有公开参考原图的读取端点。

因此，课程字格或练习页如果要展示字帖参考图，开发组必须从下面两种方案中选择一种。

### 方案 A：业务后端维护参考展示图

1. 模型组交付两门课程已批准的 200 张参考图及映射清单；
2. Java 后端将它们上传到平台对象存储；
3. `course_character.reference_asset_url` 保存平台地址；
4. 前端只访问 `onestroke.cn` 或平台对象存储。

优点：参考图片不依赖 GPU 服务，AutoDL 关机仍可显示。

这是当前更推荐的生产方案。

### 方案 B：给模型服务增加参考图端点

例如：

```http
GET /course-references/{course_id}/{target_char}.png
Authorization: Bearer <MODEL_SERVICE_KEY>
```

Java 后端再代理或首次下载缓存。浏览器仍不能直接访问。

方案 B 开发较快，但长期仍建议将参考展示图保存到业务侧，避免课程静态资源依赖
GPU 节点。

在参考图接口完成前，可以先联调课程列表、字表、练习提交和结果展示，但课程练习页
不应长期只显示系统字体渲染的汉字来冒充书法参考。

## 14. 完整调用时序

```text
1. 模型服务启动
   └── 加载 B2、两个课程配置和 200 个参考 mask cache

2. Java 后端同步课程
   └── GET 模型服务 /course-catalog
       └── 保存 calligraphy_course 和 course_character

3. 用户打开 onestroke.cn 课程页
   └── GET Java /api/calligraphy/courses

4. 用户进入欧阳询课程并选择“永”
   └── GET Java /api/calligraphy/courses/{courseId}

5. 用户在画布写“永”并提交
   └── POST Java /api/calligraphy/practices
       ├── 保存用户原图
       ├── 创建 practice_record(status=pending)
       └── 返回 practice_id

6. Java 后端调用模型
   └── POST 模型 /analyze-course-practice
       ├── image
       ├── practice_id
       ├── course_id=ouyang_xun_regular_100_beta
       └── target_char=永

7. 模型完成
   ├── 六通道分割
   ├── 找到欧阳询课程的“永”参考
   ├── 限制性对齐
   ├── 计算参考结构匹配度
   ├── 生成结构建议
   └── 返回 JSON 和临时图片 URL

8. Java 后端
   ├── 保存完整 JSON
   ├── 下载并持久化结果图片
   ├── 更新 status=succeeded
   └── 将平台 URL 返回前端

9. 前端结果页
   ├── 展示参考结构匹配度
   ├── 展示 Top-3 建议
   ├── 展示 overlay 和 alignment
   └── 支持查看五方向区域与 keypoint
```

## 15. 模型服务错误如何转成平台提示

| HTTP / `error_code` | 含义 | 平台处理 |
| --- | --- | --- |
| `400 / 40001` | 图片为空、损坏、格式错误 | 提示重新书写或导出 |
| `400 / 40002` | 课程缺失、未知或禁用 | 刷新课程目录，阻止提交 |
| `401 / 40101` | 模型服务密钥错误 | 只记录服务端日志，不向用户暴露密钥细节 |
| `403 / 40301` | Java 后端 IP 不在白名单 | 运维检查模型服务白名单 |
| `404 / 40401` | 模型临时图片不存在 | 尝试重取；若已持久化则使用平台图片 |
| `409 / 40901` | 课程不包含该字 | 返回课程页重新选择，不生成分数 |
| `413 / 41301` | 图片超过 10 MB | 前端压缩或重新导出 |
| `503 / 50301` | 参考 mask cache 缺失 | 保留练习，提示稍后重试 |
| `500 / 50001` | 模型推理或课程配置异常 | 标记失败并允许重新分析 |

失败时不得删除用户原始作品。模型恢复后可以基于同一个 `practice_record` 创建新的
分析版本。

## 16. 分阶段实施清单

### P0：先把两个课程真正接进平台

- [ ] Java 后端可以调用模型 `/course-catalog`；
- [ ] 数据库保存两个课程和各自 100 字目录；
- [ ] 前端出现两个真实课程卡片；
- [ ] 进入课程后只能选择该课程支持的字；
- [ ] 练习提交包含 `course_id + target_char + image`；
- [ ] Java 后端调用 `/analyze-course-practice`；
- [ ] 结果保存 `reference_id + model_version`；
- [ ] 结果页显示参考结构匹配度、建议、overlay 和 alignment；
- [ ] Java 后端持久化结果图片，不长期依赖 AutoDL 临时 URL；
- [ ] 模型服务 API Key 不进入前端。

### P1：完成课程体验

- [ ] 将 200 张批准参考字作为静态课程资源交付到业务侧；
- [ ] 课程字格和练习页显示真实同字参考；
- [ ] 展示六张 mask；
- [ ] 支持点击方向区域高亮；
- [ ] 展示用户练习进度与历史成绩；
- [ ] 增加失败重试和超时提示；
- [ ] 显示 Calli-Tongji Beta 来源与非商业许可说明。

### P2：后续增强

- [ ] 冻结中文 `channel_schema` 后显示方向中文名；
- [ ] 增加课程章节、顺序和解锁规则；
- [ ] 增加重复练习趋势图；
- [ ] 增加更多经过授权和审核的真实碑帖课程；
- [ ] 将模型服务迁移到稳定推理节点或本地 5080；
- [ ] 对高并发改为任务队列和多进程/多实例推理。

## 17. 最短可行实现

如果时间非常紧，开发同学只做下面六件事即可完成首版：

1. 后端调用 `/course-catalog`，把两个课程和 100 字字表返回前端；
2. 课程页点击某个字后保存 `course_id` 和 `target_char`；
3. 提交画布时将这两个字段连同 PNG 一起传给 Java 后端；
4. Java 后端按原字段调用模型 `/analyze-course-practice`；
5. 保存模型 JSON，并立即下载 overlay、alignment 和 mask 图片；
6. 结果页展示“参考结构匹配度”、建议和图片。

模型组不需要为这一步重新训练，也不需要增加 OCR。

## 18. 联调验收用例

### 用例 1：同课程支持字

```text
course_id = ouyang_xun_regular_100_beta
target_char = 课程目录中的一个字
```

预期：

- HTTP 200；
- 返回的 `course.course_id` 与请求一致；
- 返回的 `reference.target_char` 与请求一致；
- 有分数、建议、overlay、alignment 和六张 mask；
- 数据库保存 `reference_id` 和 `model_version`。

### 用例 2：王羲之课程

```text
course_id = wang_xizhi_running_100_beta
target_char = 该课程目录中的一个字
```

预期与用例 1 相同，且结果中的课程不能仍显示欧阳询。

### 用例 3：课程不支持该字

提交一个不在当前课程字表中的 `target_char`。

预期：

- 模型返回 `40901`；
- 前端显示“该课程暂未收录此字”；
- 不生成或展示伪分数。

### 用例 4：切换课程

先选择欧阳询课程中的字，再切换到王羲之课程。

预期：

- 前端重新校验字表；
- 如果新课程不支持原目标字，必须清空选择；
- 后端收到的新请求使用新的 `course_id`。

### 用例 5：AutoDL 临时图片失效

完成一次分析并将 AutoDL 关机。

预期：

- 历史练习结果页仍能从平台存储打开 overlay、alignment 和 masks；
- 如果打不开，说明 Java 后端只保存了临时模型 URL，接入尚未完成。

### 用例 6：LLM 不可用

临时关闭 LLM 配置。

预期：

- 分割和评分仍成功；
- `ai_feedback.source = deterministic`；
- 页面仍能显示规则建议。

## 19. 禁止做法

- 不要把“字体选择”中文名称直接传给模型代替 `course_id`；
- 不要把两个课程的 200 个参考字混成一个无课程边界的字库；
- 不要让前端指定任意 `reference_id`；
- 不要为课程模式增加不必要的 OCR；
- 不要给课程不支持的字选择“最像的参考字”继续评分；
- 不要将模型临时 URL 当作历史结果的永久 URL；
- 不要把 API Key 写入前端、GitHub、日志或 Markdown；
- 不要把方向区域说成可靠的第几笔或笔顺；
- 不要将结构匹配度宣传为专家审美成绩；
- 不要将当前 Beta 包宣传为具体历史碑帖。

## 20. 开发同学需要记住的核心结论

```text
课程包 = 有限字表 + 每字固定参考 + 课程内同字评分

前端负责：
选择课程、选择字、画布书写、结果展示

Java 后端负责：
课程目录、用户记录、模型转发、鉴权、状态、持久化

模型服务负责：
六通道分割、同字参考、对齐、结构评分、证据和建议

一次正确调用必须同时提交：
course_id + target_char + image + practice_id
```

只要平台建立上述课程业务层，现有两个书法包就能加入 `onestroke.cn`，无需重新训练
SegFormer-B2。
