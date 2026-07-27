# 字体条件化开源数据集筛选（2026-07-27）

## 结论

不为字体评分重新手工采集数据。采用三层数据策略：

1. **首选受控公开子集：Calli-Tongji**。它是高分辨率单字二值 PNG，已有作者、书体、Unicode 和朝代标签，适合先训练字体条件分类器与建立参考字索引。
2. **规模化主数据：UniCalli Dataset**。它有书家、书体、文字转录和字符框标注；接受数据集条款后，由导入脚本自动裁切单字，不进行人工逐字建库。
3. **零账号验证集：Calligraphy Bench**。它开放、体积小、已经是单字样本，仅用于在未取得前两者访问权限时验证完整链路。

这些数据均不用于重新训练本项目的六通道笔画分割器。它们没有 `vec1` 至 `vec5` 和 `keypoint` 标签；B2 仍使用现有 840 个带完整标签的样本训练。开源书法数据只作为参考图库、字体条件和评分评测集。

## 推荐数据源

| 优先级 | 数据集 | 获取条件 | 可直接使用的字段 | 适合的工作 | 限制 |
| --- | --- | --- | --- | --- | --- |
| P0 | [Calli-Tongji](https://www.modelscope.cn/datasets/CalliTongji/Calli-Tongji_A_Dataset_of_Historical_Calligraphy_Styles) | ModelScope 页面要求登录；CC BY-NC 4.0 | 预裁切单字二值 PNG、作者-书体、Unicode、朝代 | 小规模字体分类器、同字参考检索、评分 MVP | 当前 Beta 为 50 类 x 100 图的子集；未登录下载返回 401，需先确认子集是否含目标书家 |
| P1 | [UniCalli Dataset](https://huggingface.co/datasets/TSXu/UniCalli_dataset) | 需 Hugging Face 登录并接受条款 | 原图、字符框、现代转录、书家、书体 | 自动生成大规模候选参考字库、后续字体条件模型 | 门控访问；项目与数据均限定学术/非商业使用，避免重新分发图像 |
| P2 | [MCCD](https://github.com/SCUT-DLVCLab/MCCD) | 官方提供百度网盘/OneDrive链接，但 README 要求申请解压密码；CC BY-NC-ND 4.0 | 近 33 万单字、字符、书体、朝代、书家标签 | 书体/书家分类器、风格嵌入模型 | 非商用研究用途；需申请，官方公开材料未列出王羲之和欧阳询的实际样本数量 |
| P3 | [Calligraphy Bench](https://huggingface.co/datasets/haizelabs/calligraphy-bench) | 公开、无需登录、Apache-2.0 | 单字图、`character`、`calligrapher`、笔画 SVG、中心线 | 立即做小范围参考字评分原型 | 仅 88 字，图像为 64x64；不能作为大规模训练集或完整字体库 |
| 不选作首批 | [ChineseCalligraphyBench](https://huggingface.co/datasets/boydcheung/ChineseCalligraphyBench) | 公开、Apache-2.0 | 120 幅作品图、作品标题、繁简转录 | OCR 或整幅书法识别研究 | 没有字符框，不能直接成为单字参考库 |
| 不选作产品来源 | [zhuojg/chinese-calligraphy-dataset](https://github.com/zhuojg/chinese-calligraphy-dataset) | Google Drive 下载 | 13.8 万字图、19 位书家、字符目录 | 风格分类的研究性补充 | 原数据由互联网收集，缺少逐作品来源与许可记录；不适合直接充当公开评分标准 |

## Calligraphy Bench 备用试点

Calligraphy Bench 已核验为可下载的 Apache-2.0 Parquet 文件，约 0.6 MB，包含 88 个预裁切单字和 18 位书家。欧阳询共有 5 个样本：

```text
瀁、睬、犀、粥、崎
```

它们应在界面中称为：

```text
欧阳询书法参考（Calligraphy Bench 试点）
```

不能称为“欧阳询小楷”，因为数据集没有提供作品名和书体版本来支持这个更强的断言。王羲之在该数据中有 8 个样本，但同样不应标成《兰亭序》。

试点流程不需要 OCR：用户选定目标字后，系统以 `target_char + target_style_id` 查找参考图；如果该字不在 5 个欧阳询样本内，就提示该试点字暂未开放。数据集同时提供笔画 SVG 和中线，可在后续用作几何评分的辅助证据。

## UniCalli 的接入边界

UniCalli 是当前最适合规模化的来源：项目说明称其覆盖 95+ 位书家和五大书体，且每张原图已有字符框、转录、书家和书体标签。接入方式应为：

```text
下载官方数据 -> 读取官方标注 -> 按 bbox 自动裁切单字 -> 按书家/书体/字符建索引 -> 自动质量筛选 -> 小比例人工抽检
```

这不是自行制作数据集。项目只保存导入代码、来源 ID、许可信息、哈希和审核清单；原图与裁切图置于受控存储，不提交到 Git 仓库。

开始前，项目负责人或获授权成员需要在 Hugging Face 数据集页面登录并接受 UniCalli 的访问条款。条款未接受前，不尝试绕过门控下载。

## MCCD 与“墨宝/Moyun”核验结果

MCCD 是真实的官方 ICDAR 2025 数据集。官方 README 明确说明：约 33 万张独立单字、7,765 个汉字类别、10 类书体、15 个朝代和 142 位书家；数据格式为 PNG/LMDB，并提供读取代码。它不是无条件下载：README 要求非商用研究申请，批准后提供解压密码。可作为 UniCalli 的备用大规模来源。

“墨宝（Mobao）/Moyun 190 万张”的描述目前没有提供可核验的论文、官方仓库或数据下载地址；对 GitHub 和 Hugging Face 的公开检索也没有找到相符的官方发布。因此在获得原始论文或官方链接前，不将它纳入项目方案。

## 下一步实施顺序

1. 登录 ModelScope，下载 Calli-Tongji Beta，并读取 `dataset.txt`，确认是否有“欧阳询-楷”和“王羲之-行”；若有，优先使用该子集完成 MVP。
2. 仅开放数据中真实存在的 `target_style_id + target_char` 组合，完成参考字导入、B2 推理缓存、受限对齐和结构评分接口。
3. 同时取得 UniCalli 访问许可，实现自动导入器，并把可评分范围扩展到有足量同字参考的书家/书体组合。
4. 若 Calli-Tongji 子集不含目标书家，使用 Calligraphy Bench 的欧阳询 5 字完成最小演示，不把它包装成完整字体库。
5. 在每个组合有足量相同汉字的多份参考后，再训练字体条件编码器；评分结论仍以确定性的几何特征和 B2 输出为主，语言模型只负责生成文字反馈。
