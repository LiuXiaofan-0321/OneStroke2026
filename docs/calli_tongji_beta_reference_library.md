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

## 使用限制

第一版评分服务只能处理“所选风格 + 用户目标字”在清单中存在的组合。若某个用户目标字没有相应参考图，服务必须返回“不在当前 Beta 参考范围内”，而非编造风格分数。
