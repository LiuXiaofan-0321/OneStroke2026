# 刘小凡任务二：困难样本集整理

负责人：刘小凡  
协作对象：高怡然、张荣昊  
建议时间：张荣昊执行任务 1/3 的同时并行推进  
任务目标：整理一份约 50 个困难样本的固定评测集，用于后续统一评测 U-Net、SegFormer-B2、SAM2 辅助方案和端侧学生模型。

## 1. 和张荣昊任务 1/3 是否互不影响

基本互不影响。

张荣昊当前负责：

- 任务 1：复核 54 个问题样本。
- 任务 3：跑 U-Net 重测基线。

你当前负责：

- 任务 2：整理困难样本集。

三者关系：

| 任务 | 输入 | 输出 | 是否会互相覆盖 |
| --- | --- | --- | --- |
| 任务 1：坏样本复核 | `manifest.csv` | `bad_samples_review.csv` | 不会 |
| 任务 2：困难样本集 | `manifest.csv`、样本图像 | `hardset_review.csv` | 不会 |
| 任务 3：U-Net baseline | `manifest.csv`、`splits.csv` | checkpoint、metrics、notes | 不会 |

唯一要注意的是：你和张荣昊都可能依赖 `artifacts/data_audit/manifest.csv`。如果后面重新生成 manifest，困难样本的 `sample_id` 应该保持稳定；因此困难样本集里不要依赖本机绝对路径，只记录 `sample_id`、`char_id`、困难类型和备注。

## 2. 为什么困难样本集很重要

普通测试集能告诉我们模型总体表现，但不能准确回答项目最关心的问题：

- 交叉区域有没有分准？
- 粘连笔画有没有拆开？
- 端点和起收笔有没有识别出来？
- 线宽变化大时是否稳定？
- 换背景后是否误分？

旧 U-Net 的问题往往也集中在这些场景。困难样本集就是后续证明 SegFormer-B2 和 SAM2 辅助方案确实有效的关键证据。

月底报告里可以单独写：

> 在 50 个交叉、粘连、端点等困难样本上，新模型相比 U-Net baseline 提升了 X 个百分点。

这比只报一个总体 Dice 更有说服力。

## 3. 任务输入

本任务主要看三个文件。

### 3.1 数据 manifest

```text
artifacts/data_audit/manifest.csv
```

用途：

- 查 `sample_id`
- 查 `char_id`
- 查本机图片路径
- 确认样本是否完整可用

### 3.2 自动生成的候选困难样本模板

```text
artifacts/data_audit/hardset_template.csv
```

如果本地没有，可以运行：

```powershell
python -m onestroke_model.scripts.make_hardset_template `
  --manifest ".\artifacts\data_audit\manifest.csv" `
  --output ".\artifacts\data_audit\hardset_template.csv" `
  --limit 50
```

注意：这个文件在 `artifacts/` 下，默认不提交 GitHub，因为里面可能含有本机绝对路径。

### 3.3 可提交的评审模板

```text
templates/hardset_review_template.csv
```

这是 GitHub 上可提交的空模板。正式整理结果建议复制为：

```text
reviews/hardset_review.csv
```

如果暂时不想提交结果，也可以先放在：

```text
artifacts/data_audit/hardset_review.csv
```

## 4. 输出文件建议

推荐最终输出为：

```text
reviews/hardset_review.csv
```

这个文件可以提交到 GitHub，因为它不记录本机绝对路径，只记录样本 ID 和困难标签。

字段如下：

| 字段 | 含义 |
| --- | --- |
| `sample_id` | 样本 ID，例如 `0/12` |
| `char_id` | 字符目录 ID |
| `sample_index` | 样本编号 |
| `split` | train / val / test |
| `difficulty_crossing` | 是否交叉严重，`0/1` |
| `difficulty_adhesion` | 是否粘连严重，`0/1` |
| `difficulty_endpoint` | 是否端点/起收笔模糊，`0/1` |
| `difficulty_line_width` | 是否线宽变化明显，`0/1` |
| `difficulty_background` | 是否背景干扰明显，`0/1` |
| `difficulty_style` | 是否存在明显风格差异/字体风格相关问题，`0/1` |
| `priority` | 优先级，`high/medium/low` |
| `reviewer` | 评审人 |
| `keep` | 是否纳入困难集，`yes/no` |
| `notes` | 备注 |

## 5. 困难类型定义

### 5.1 `difficulty_crossing`

交叉严重。

典型情况：

- 横竖交叉处重叠明显。
- 撇捺交叉处难以判断归属。
- 多个方向笔画在同一区域相交。
- 旧 U-Net 容易把交叉处涂成一团。

### 5.2 `difficulty_adhesion`

粘连严重。

典型情况：

- 两个本应分开的笔画连在一起。
- 笔画之间墨迹或线条粘住。
- 笔画边界不清。
- 模型容易把两个笔画当成一个区域。

### 5.3 `difficulty_endpoint`

端点、起笔、收笔困难。

典型情况：

- 起笔很短或很尖。
- 收笔区域模糊。
- 点画和短横容易混淆。
- keypoint 标签区域很小，模型容易漏检。

### 5.4 `difficulty_line_width`

线宽变化明显。

典型情况：

- 同一个字里有明显粗细变化。
- 某些笔画过细。
- 某些笔画过粗，导致边界膨胀。
- 字迹粗细和训练集主流样本差异大。

### 5.5 `difficulty_background`

背景干扰明显。

典型情况：

- 纸张背景不纯。
- 有阴影、拍照噪声、扫描噪声。
- 字体颜色和背景对比度低。
- 存在边框、印刷纹理、其他干扰线。

### 5.6 `difficulty_style`

字体/书家风格相关困难。

典型情况：

- 字形接近某种书家风格，但结构和通用样本差异大。
- 某些笔画写法因风格不同导致方向或关键点难判。
- 未来选择赵孟頫楷体、欧阳询楷体等目标风格时，这类样本可能成为风格评价难点。

这个字段是为新增“字体选择功能”预留的，不一定每个样本都要填。

## 6. 整理流程

### 第一步：从候选模板开始

先打开：

```text
artifacts/data_audit/hardset_template.csv
```

逐个查看图像，判断是否真的困难。

如果模板样本不够典型，可以替换。但最终保持约 50 个样本即可，不必强行完全固定为模板里的 50 个。

### 第二步：尽量覆盖不同字符

不要全部集中在少数字符上。建议：

- 尽量覆盖 20 个以上不同 `char_id`。
- 每个困难类型至少有若干样本。
- 不要只选模型已经很容易分的样本。

### 第三步：优先选 test / val 样本

困难集主要用于评测，不用于训练。

优先级建议：

1. `test` 样本
2. `val` 样本
3. `train` 样本

如果必须选 train 样本，需要在 notes 里标明，避免后续误用。

### 第四步：标记困难类型

每个样本可以有多个困难标签。

例如：

```csv
sample_id,char_id,sample_index,split,difficulty_crossing,difficulty_adhesion,difficulty_endpoint,difficulty_line_width,difficulty_background,difficulty_style,priority,reviewer,keep,notes
12/18,12,18,test,1,1,0,0,0,0,high,刘小凡,yes,交叉和粘连都明显
```

### 第五步：和高怡然做人工复核

整理完成后，建议让高怡然或书法专业成员抽查：

- 困难类型是否标得合理。
- 是否有不典型样本。
- 是否有明显标错。
- 是否应该补充风格相关困难样本。

## 7. 数量建议

第一版困难集建议约 50 个样本。

参考比例：

| 类型 | 建议数量 |
| --- | --- |
| 交叉严重 | 15–20 |
| 粘连严重 | 10–15 |
| 端点/起收笔 | 10–15 |
| 线宽变化 | 5–10 |
| 背景干扰 | 5–10 |
| 风格相关 | 5–10 |

一个样本可以计入多个类型，所以总和可以超过 50。

## 8. 验收标准

完成后应该能回答：

- 困难集里有多少个样本？
- 覆盖了多少个字符？
- 每类困难样本各有多少个？
- 是否主要来自 val/test？
- 哪些样本适合用于报告展示？
- 哪些样本适合后续观察 SAM2 边界修正效果？

最低交付：

```text
reviews/hardset_review.csv
```

建议额外交付：

```text
reviews/hardset_summary.md
```

summary 可以写：

```markdown
# Hardset Summary

- total samples:
- unique chars:
- crossing:
- adhesion:
- endpoint:
- line_width:
- background:
- style:
- high priority examples:
- notes:
```

## 9. 和后续实验的关系

困难集后续会用于：

- U-Net baseline 困难集评测
- SegFormer-B2 困难集评测
- SAM2 边界辅助是否有效
- 端侧学生模型是否在困难样本上退化
- 月底报告中的可视化对比图

因此这个文件要稳定。除非发现明显错误，不要频繁改动样本集合。

## 10. 当前建议你马上做什么

1. 从 GitHub 拉最新代码：

```powershell
git pull
```

2. 本地生成或确认存在：

```text
artifacts/data_audit/manifest.csv
artifacts/data_audit/splits.csv
artifacts/data_audit/hardset_template.csv
```

3. 复制模板：

```powershell
New-Item -ItemType Directory -Force reviews
Copy-Item ".\templates\hardset_review_template.csv" ".\reviews\hardset_review.csv"
```

4. 打开 `manifest.csv` 和图片，开始填 `reviews/hardset_review.csv`。

5. 第一版先整理 20 个高优先级样本，不必一口气做完 50 个。

