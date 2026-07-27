# Calli-Tongji Beta 参考字库

## 已验证的数据版本

- 数据集：[Calli-Tongji](https://www.modelscope.cn/datasets/CalliTongji/Calli-Tongji_A_Dataset_of_Historical_Calligraphy_Styles)
- 许可证：`CC-BY-NC-4.0`，仅用于本项目的非商业学术研究。
- 下载文件：`Calli-Tongji.zip`
- 已验证 SHA-256：`bae995df68a3469fe486939dd42b209145ab56d10f580990380e25dcf9e2fbe9`
- Beta 子集总量：5,000 张 `256x256` RGB 单字 PNG，50 个书家-书体类别，每类 100 张。

## 当前开放的两个条件风格

| `target_style_id` | 前端名称 | 数据集类别 | 参考字数 |
| --- | --- | --- | ---: |
| `ouyang_xun_regular_calli_tongji_beta` | 欧阳询楷书（Calli-Tongji Beta） | 欧阳询-楷 | 100 |
| `wang_xizhi_running_calli_tongji_beta` | 王羲之行书（Calli-Tongji Beta） | 王羲之-行 | 100 |

这两个名称描述的是 Calli-Tongji 中的标注类别，不宣称它们分别是某一特定碑帖版本或《兰亭序》版本。

## 团队协作边界

- 共享并提交：`references/calli_tongji_beta_manifest.csv`、导入脚本、数据来源、许可证和校验哈希。
- 不提交：`references/images/` 下的原始/裁切 PNG；该目录被 `.gitignore` 忽略。
- 团队成员需要从官方来源自行下载同一压缩包，并用 SHA-256 与本文档比对。

## 可复现导入

在 `model_module` 目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path ".\src").Path

python -m onestroke_model.scripts.import_calli_tongji `
  --archive "C:\path\to\Calli-Tongji.zip" `
  --image-dir ".\references\images\calli_tongji_beta" `
  --manifest ".\references\calli_tongji_beta_manifest.csv" `
  --reviewer "your_name"

python -m onestroke_model.scripts.validate_reference_manifest `
  --manifest ".\references\calli_tongji_beta_manifest.csv" `
  --registry ".\configs\style_registry.yaml" `
  --check-files `
  --require-approved
```

导入器只抽取上述两个类别共 200 张图，并验证每一张均为 `256x256` RGB PNG。它会生成可追溯清单，记录每张图的来源成员路径、图像哈希关联 ID、数据集许可证及压缩包版本哈希。

## B2 缓存与结构证据评分

先在有 PyTorch、Transformers 和 GPU 的环境中为 200 张参考字生成 B2 六通道二值 mask 缓存：

```powershell
python -m onestroke_model.scripts.cache_reference_masks `
  --manifest ".\references\calli_tongji_beta_manifest.csv" `
  --config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --cache-dir ".\references\cache\segformer_b2_v1" `
  --output-index ".\references\cache\segformer_b2_v1\index.json" `
  --batch-size 4
```

缓存也是由受限数据导出的内容，位于被 Git 忽略的 `references/cache/`，不可提交。随后按用户已选定的字和风格评分：

```powershell
python -m onestroke_model.scripts.score_reference_style `
  --image ".\user_character.png" `
  --style-id "ouyang_xun_regular_calli_tongji_beta" `
  --target-char "宇" `
  --cache-index ".\references\cache\segformer_b2_v1\index.json" `
  --config ".\configs\segformer_b2_v1_delivery.yaml" `
  --checkpoint ".\checkpoints\segformer_b2_v1\best.pt" `
  --output-dir ".\artifacts\style_score_demo"
```

输出 `evidence.json` 和 `alignment_overlay.png`。前者包含五个方向通道 Dice、墨迹 IoU、3 像素容差关键点 F1、对齐前的重心/面积差，以及被选中的平移、等比缩放和小角度旋转。`prototype_structure_score` 仅是这些证据的透明加权汇总，不是书法老师校准后的正式审美分数。

## 使用限制

第一版评分服务只能处理“所选风格 + 用户目标字”在清单中存在的组合。若某个用户目标字没有相应参考图，服务必须返回“不在当前 Beta 参考范围内”，而非编造风格分数。
