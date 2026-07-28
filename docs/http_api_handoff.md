# OneStroke 模型 HTTP API 交接

模型侧已提供面向 Java 后端的同步 HTTP 服务。服务启动时加载一次
`segformer-b2-v1`，之后每个请求完成：六通道分割、课程内同字参考选择、限制性
对齐、参考结构匹配度、可解释反馈，以及结果图片导出。

浏览器前端不得直连模型服务。推荐链路是：

```text
前端 -> OneStroke Java 后端（用户鉴权、练习记录）
     -> 模型 HTTP 服务（服务间 API Key + IP 白名单）
     -> Java 后端保存/转发结果给前端
```

## 启动前准备

部署节点必须已有以下资源：

1. `checkpoints/segformer_b2_v1/best.pt`（Git LFS 文件，不是 LFS 指针）；
2. 已导入的 Calli-Tongji Beta 参考图和 `references/cache/segformer_b2_v1/`；
3. Python 3.11+、可用的 PyTorch/Transformers，以及项目代码。

首次安装：

```bash
cd /root/autodl-tmp/lxf/OneStroke2026
python -m pip install -e '.[train,serve]'
```

在模型机器设置运行时变量。`ONESTROKE_API_KEY` 自行生成且只交给 Java 后端的
服务器配置，绝不提交 Git 或放入前端。当前 Java 服务公网出口 IP 为
`139.196.76.159`，可以作为白名单。

```bash
cd /root/autodl-tmp/lxf/OneStroke2026

export PYTHONPATH="$PWD/src"
export ONESTROKE_API_KEY='replace-with-a-long-random-secret'
export ONESTROKE_ALLOWED_IPS='139.196.76.159'
export ONESTROKE_PUBLIC_BASE_URL='https://YOUR_MODEL_PUBLIC_HOST'
export ONESTROKE_CHECKPOINT="$PWD/checkpoints/segformer_b2_v1/best.pt"
export ONESTROKE_ARTIFACT_ROOT="$PWD/artifacts/http_api/practice"

mkdir -p "$PWD/logs"

nohup python -m onestroke_model.scripts.serve_http_api \
  --host 0.0.0.0 --port 8000 \
  > "$PWD/logs/model_http_api.log" 2>&1 &

echo $! > "$PWD/logs/model_http_api.pid"
```

`YOUR_MODEL_PUBLIC_HOST` 必须替换为实际可供 Java 后端访问的 AutoDL 端口映射地址
或 HTTPS 域名，例如 `https://model.example.com`，不要虚构该地址。模型启动完成后：

```bash
curl http://127.0.0.1:8000/healthz
tail -f "$PWD/logs/model_http_api.log"
```

预期健康检查返回 `{"status":"ok",...}`。停止服务：

```bash
kill "$(cat "$PWD/logs/model_http_api.pid")"
```

## 鉴权与网络约束

除 `GET /healthz` 外的全部接口都需要以下任一请求头：

```http
Authorization: Bearer <ONESTROKE_API_KEY>
```

或：

```http
X-API-Key: <ONESTROKE_API_KEY>
```

同时服务只接受 `ONESTROKE_ALLOWED_IPS` 内的直接来源 IP。端口映射/反向代理必须
保留 Java 服务的真实来源 IP；若不能保留，请改为在同一私网部署或关闭 IP 白名单，
但仍必须保留 API Key。`overlay_url`、`alignment_overlay_url` 和 mask 链接也使用同一
鉴权与白名单，Java 后端应带同一服务间请求头读取并转发或保存，不建议让浏览器直接读取。

错误响应统一为：

```json
{
  "status": "failed",
  "error_code": "40901",
  "error_message": "This course does not include the requested target_char."
}
```

| HTTP / `error_code` | 含义 |
| --- | --- |
| `400 / 40001` | 图片为空、损坏、非 PNG/JPEG，或 multipart 请求不合法 |
| `400 / 40002` | `course_id` 缺失、未知或已禁用 |
| `401 / 40101` | API Key 缺失或错误 |
| `403 / 40301` | 调用方 IP 不在白名单 |
| `404 / 40401` | 结果图片不存在 |
| `409 / 40901` | 当前课程未收录该 `target_char` |
| `413 / 41301` | 图片超过 10 MB（可用 `ONESTROKE_MAX_UPLOAD_MB` 调整） |
| `503 / 50301` | 参考 mask cache 不完整 |
| `500 / 50001` | 模型推理或课程配置异常 |

## 课程字表

```http
GET /course-catalog
Authorization: Bearer <API_KEY>
```

返回两个课程及其各 100 个 `target_char`。Java 后端启动时可拉取并缓存，课程页使用
返回的 `characters[].target_char` 建立字格，不要手写字表或让前端传任意
`reference_id`。

当前支持：

| `course_id` | 展示名 | 数量 |
| --- | --- | ---: |
| `ouyang_xun_regular_100_beta` | 欧阳询楷书·100字练习包（Beta） | 100 |
| `wang_xizhi_running_100_beta` | 王羲之行书·100字练习包（Beta） | 100 |

## 练字分析接口

```http
POST /analyze-course-practice
Content-Type: multipart/form-data
Authorization: Bearer <API_KEY>
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `image` | File | 是 | 用户练字图片，仅 PNG/JPEG，最大 10 MB |
| `practice_id` | String | 是 | Java 后端已创建的练习记录 ID，模型会原样回传 |
| `course_id` | String | 是 | 课程 ID |
| `target_char` | String | 是 | 当前练习的单个目标字 |

调用示例：

```bash
curl -X POST 'https://YOUR_MODEL_PUBLIC_HOST/analyze-course-practice' \
  -H 'Authorization: Bearer YOUR_MODEL_SERVICE_KEY' \
  -F 'image=@./user_character.png;type=image/png' \
  -F 'practice_id=practice_001' \
  -F 'course_id=ouyang_xun_regular_100_beta' \
  -F 'target_char=永'
```

成功时返回 HTTP `200`：

```json
{
  "task_id": "eval_20260728_123456_ab12cd34ef",
  "practice_id": "practice_001",
  "status": "succeeded",
  "schema_version": 1,
  "model_version": "segformer-b2-v1",
  "course": {
    "course_id": "ouyang_xun_regular_100_beta",
    "display_name": "欧阳询楷书·100字练习包（Beta）"
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
  "overlay_url": "https://YOUR_MODEL_PUBLIC_HOST/artifacts/eval_.../overlay.png",
  "alignment_overlay_url": "https://YOUR_MODEL_PUBLIC_HOST/artifacts/eval_.../alignment_overlay.png"
}
```

`scores.prototype_structure_score` 的固定展示名为“参考结构匹配度”。它是 B2 六通道
结构证据与同字参考的透明聚合，**不是**专家评分、书法考试成绩或审美分数。

`segmentation` 扩展字段还会返回固定通道顺序、阈值、关键点、笔画区域和六张
`mask_urls`。`stroke_regions` 是可点击的连通笔画区域，不能显示为“第几笔”，因为
`stroke_order_analysis=false`。

`feedback` 默认由可审计的规则证据生成。若模型节点额外配置
`ONESTROKE_LLM_URL`、`ONESTROKE_LLM_MODEL` 及只存在服务器环境变量中的 LLM Key，
响应会附带 `ai_feedback.source="llm"` 的文本润色结果；LLM 失败时自动回退到规则建议，
不会使 B2 分析失败。
