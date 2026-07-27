# 王羲之《兰亭序》与欧阳询小楷参考字试点

## 目标

建立两个小规模、可追溯的参考字库，作为 B2 分割结果的对齐和结构评分基准。此阶段不训练新的字体条件模型，不把生成图片作为正式评分标准。

## 固定风格 ID

| style_id | 名称 | 当前状态 |
| --- | --- | --- |
| `wang_xizhi_lanting_xingshu` | 王羲之《兰亭序》行书 | 待锁定具体摹本或刻本版本 |
| `ouyang_xun_xiaokai` | 欧阳询小楷 | 待锁定具体作品与图像版本 |

两者均为 `enabled: false`，直到具体来源、许可和书法审核完成。前端不得把未启用风格作为可评分选项。

## UniCalli 的使用边界

[UniCalli 数据集](https://huggingface.co/datasets/TSXu/UniCalli_dataset) 可作为候选来源。其公开说明包含字符框、文字转录、书家和书体标签，可从整列作品中裁切候选单字。

它不是正式评分标准，原因是：

- 候选裁切可能有框偏移、噪声或文字归属错误；
- 历史作品版本和归属需要单独确认；
- 该数据集访问受条件限制，页面标注为 `CC-BY-NC-ND-4.0`；
- 未经核实的裁切图不能重新公开发布到项目仓库。

只提交处理脚本、来源 ID、审核元数据和必要的哈希；原图与裁切结果存放在受控的本地或对象存储中。

## 候选到正式参考的流程

```text
UniCalli 或其他授权来源
  -> 字符框裁切候选
  -> 文字与书家/书体一致性检查
  -> 图像质量与来源版本检查
  -> 书法成员审核
  -> reference_manifest.csv 中标为 approved
  -> 在 style_registry.yaml 中启用风格
  -> 缓存 B2 的六通道结果
```

建议第一轮只处理两个风格共同覆盖的 10 至 20 个汉字。每个字保留 1 至 3 个审核通过的真实参考版本；评分时取多个参考的中位数，避免单个历史样本偶然性。

## 受限对齐规则

用户字和参考字都先统一为白底、前景裁切、等比例缩放。对齐只允许：

- 平移；
- 等比例缩放，范围 `0.80` 至 `1.20`；
- 不超过 3 度的旋转。

禁止非等比拉伸和局部形变。对齐前保留整体重心、尺度和倾斜误差；对齐后再比较五方向 mask、关键点和轮廓。这样不会把用户写得过宽、过窄或重心偏移的问题自动消除。

## 首批审核清单

每个候选参考字均需确认：

- `target_char` 与原作转录一致；
- `author_id`、`script_style` 和具体作品一致；
- 记录原图 URL、版本与许可证；
- 裁切内没有相邻字、印章或明显噪声；
- 书法成员确认该字可用作临摹标准；
- 不是 UniCalli 或其他模型生成的 synthetic 图；
- 对应 B2 mask 无明显系统性错误。

## 校验命令

复制 `templates/reference_manifest_template.csv` 到 `references/reference_manifest.csv` 后，将审核通过的裁切图放在
`references/images/` 下；`image_path` 必须相对于清单文件所在的目录填写。然后运行：

```powershell
python -m onestroke_model.scripts.validate_reference_manifest `
  --manifest ".\references\reference_manifest.csv" `
  --registry ".\configs\style_registry.yaml" `
  --check-files
```

全部参考字审核完成、对应 style 被启用后，再加上 `--require-approved`。校验不通过的引用不能参与正式评分。
