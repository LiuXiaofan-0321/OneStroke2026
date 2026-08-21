# OneStroke2026 论文三人协作说明

## 唯一源文件

GitHub 仓库中的 `paper/` 是论文唯一可信源。在线 LaTeX 平台只用于集中
讨论或临时共同编辑，不能和 GitHub 同时形成两套各自演化的正文。

每次修改完成后，应先合并回 GitHub，再开始下一轮编辑。

## 推荐分支

三位作者分别使用自己的论文分支：

```text
paper/xiaofan
paper/ronghao
paper/yuan
```

第一次建立分支：

```bash
git switch main
git pull --ff-only origin main
git switch -c paper/xiaofan
git push -u origin paper/xiaofan
```

其他作者将最后一行的名字替换为自己的名字。

## 一次修改的标准流程

1. 从最新 `main` 开始工作。
2. 一次提交只处理一个主题，例如“补 Related Work”或“修正 Table 3”。
3. 推送个人分支并创建 Pull Request。
4. 至少由另一位作者检查科学表述、数字和引用。
5. GitHub Actions 编译成功后再合并。
6. 合并后删除已完成的临时分支，下一项工作重新建立分支。

本地命令示例：

```bash
git switch main
git pull --ff-only origin main
git switch -c paper/xiaofan-related-work

# 修改并检查后
git add paper/
git commit -m "Revise calligraphy assessment related work"
git push -u origin paper/xiaofan-related-work
```

不方便安装 Git 时，可以在 GitHub 仓库页面按 `.` 打开网页编辑器，完成
修改后从左侧 Source Control 面板提交到个人分支。

## 文件拆分与冲突控制

正文已经拆分为独立文件：

```text
paper/manuscript.tex                 作者、摘要和声明
paper/sections/01_introduction.tex   引言
paper/sections/02_related_work.tex   相关工作
paper/sections/03_method.tex         方法
paper/sections/04_experimental_protocol.tex  实验协议
paper/sections/05_results.tex        结果
paper/sections/06_discussion.tex     讨论
paper/sections/07_conclusion.tex     结论
paper/tables/                        表格
paper/figures/                       正文图
paper/references.bib                 参考文献
```

同一时间尽量不要让两个人修改同一个 `.tex` 文件。数字修改必须同时核对
其来源 artifact，不允许只为改善叙述而手工调整实验结果。

## 自动编译与下载

推送论文文件或创建 Pull Request 后：

1. 打开仓库的 **Actions** 页面；
2. 选择 **Build IJDAR paper**；
3. 等待绿色对勾；
4. 打开该次运行；
5. 在 **Artifacts** 下载 `OneStroke2026-IJDAR-paper`。

压缩包中包含：

```text
manuscript.pdf
supplementary.pdf
OneStroke2026_online_latex.zip
```

如果工作流失败，应先修复 LaTeX 错误、未定义引用或超出版心的内容，再
合并 Pull Request。

## 导入在线 LaTeX 平台

下载 `OneStroke2026_online_latex.zip` 后，在在线平台中选择“上传
项目/Upload Project”，直接上传 ZIP。主文件选择 `manuscript.tex`。

在线编辑结束后：

1. 导出完整项目 ZIP；
2. 只把经过确认的 `.tex`、`.bib`、表格和图片变化合并回个人 Git 分支；
3. 创建 Pull Request；
4. GitHub Actions 编译通过后再合并。

不要直接用在线平台导出的旧版本覆盖整个 `paper/` 目录。

## 投稿前冻结

投稿候选版本应满足：

- `main` 分支无未提交修改；
- GitHub Actions 编译通过；
- 主文和 Supplementary 均由同一个提交生成；
- 记录提交 SHA；
- 三位作者共同确认作者顺序、贡献、经费、伦理和数据可用性声明；
- 将最终 PDF 与源文件 ZIP 一起归档。
