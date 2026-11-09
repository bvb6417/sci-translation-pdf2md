# SCI Translation PDF2MD

一个 AI 编程助手的 **Skill**：把英文 SCI / 学术论文 PDF 翻译成排版完整的中文 Markdown，并额外导出一份图片内嵌、带目录的单文件 HTML。

- **逐段全文翻译，不压缩成概述**：正文、图表标题与图注、附录、符号表、脚注、致谢、声明、参考文献都要译；长文自动分批续译，交付前做逐段覆盖核对（`source/translation_coverage.md`）
- 公式用 LaTeX 重排并保留原编号（`\tag{1}`、`\tag{A1}`），表格保留每一行每一格
- 图片优先提取 PDF 内嵌原图；不完整时导出矢量图区域或按坐标裁剪，并由模型目视检查裁剪边界，图号按原文图题对应
- 开头附“要点详解”和文章信息图：会话里有生图工具时必须实际生成；只有工具确实不可用时，才改为输出完整的中文生图提示词
- 导出 `*_图片内嵌.html`：图片转 base64、公式转 MathML、自带可折叠的标题目录，不依赖任何 CDN，双击即开，可以直接发给别人

## 安装

把整个文件夹放进助手的 skills 目录，文件夹名保持 `sci-translation-pdf2md`：

| 助手 | 位置 |
|---|---|
| OpenAI Codex | `~/.codex/skills/sci-translation-pdf2md/` |
| Claude Code | `~/.claude/skills/sci-translation-pdf2md/` |

```powershell
git clone https://github.com/bvb6417/sci-translation-pdf2md.git "$HOME\.codex\skills\sci-translation-pdf2md"
python -m pip install -r "$HOME\.codex\skills\sci-translation-pdf2md\requirements.txt"
```

不用 git 的话，在 GitHub 页面点 **Code → Download ZIP**，解压后把文件夹改名为 `sci-translation-pdf2md` 放进上面的目录即可。

可选：安装 Poppler 后可使用 `pdftotext -layout` 提取文本；未安装时自动用 PyMuPDF。

## 使用

在对话中给出 PDF 并说：

```text
/翻译论文 D:\papers\Wood_2005.pdf
```

或 `/translate paper`。输出目录形如：

```text
Wood_2005_水锤分析必不可少且简单并且高效_中文翻译/
├── Wood_2005_..._中文翻译.md
├── Wood_2005_..._中文翻译_图片内嵌.html
├── assets/          # figure_01.png …、文章信息图（或信息图提示词）
└── source/          # 提取报告、矢量图候选框、译文覆盖核对记录
```

如果想把所有译好的 HTML 集中存一份，可以在自己的 `AGENTS.md` / `CLAUDE.md` 里写明归档文件夹，skill 会额外复制一份过去。

完整工作流程和质量要求见 [SKILL.md](SKILL.md)。

## 模型建议

- 推荐在 **Codex** 中使用 GPT 系列（GPT-5.6 Sol 或更新版本），**中等或更高思考强度**即可；其他助手和模型我没有系统测试，不保证效果。
- 需要模型具备视觉能力（目视检查图片裁剪、识别公式和表格）。
- 主要针对**文本型 PDF**；纯扫描件也能处理，但没有接 OCR，依赖模型自身的视觉能力，成本会高一些。

## 脚本也可以单独使用

```powershell
# 提取 PDF 内嵌图片、矢量图候选区域和页面预览
python scripts/pdf2md_assets.py --pdf paper.pdf --out-dir out --extract-embedded --extract-vectors --render-pages

# 按 crops.json 中的坐标裁剪图片（PyMuPDF 页面坐标，页码从 1 开始）
python scripts/pdf2md_assets.py --pdf paper.pdf --out-dir out --crops crops.json

# Markdown → 图片内嵌 HTML（图片和公式全部离线内嵌，默认生成标题目录）
python scripts/export_html.py out/paper.md
```

`crops.json` 示例：

```json
{"figures": [{"name": "figure_01", "page": 3, "box": [66, 86, 545, 454]}]}
```

`scripts/md2html.py` 直接运行时是一个带图形界面的 Markdown → HTML 转换器（拖放需要可选依赖 `tkinterdnd2`），任何 Markdown 文件都能用它转成单文件 HTML。

## 目录结构

```text
sci-translation-pdf2md/
├── SKILL.md                 # skill 主说明（助手读取）
├── agents/openai.yaml       # Codex 界面显示信息
├── references/
│   ├── output-template.md   # 译文开头模板与完整性验收
│   └── html-export.md       # HTML 导出说明
└── scripts/
    ├── pdf2md_assets.py     # PDF 图片 / 矢量图 / 页面预览提取与裁剪
    ├── export_html.py       # 无界面 HTML 导出入口
    └── md2html.py           # Markdown → HTML 转换器
```

## 许可证

[MIT](LICENSE)
