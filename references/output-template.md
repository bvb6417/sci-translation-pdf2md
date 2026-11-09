# Chinese SCI PDF2MD Output Template

```markdown
# <中文标题>

原文：<authors> (<year>). *<English title>*. <journal>, <volume>, <article/pages>. <DOI URL>

译注：本文公式以 LaTeX 重排；图像优先使用 PDF 内嵌图，若内嵌图不完整则使用 Figure 区域裁剪图。正文逐段完整翻译，不压缩为概述；正文开头在会话有 imagegen 工具时必须提供实际生成的信息图，只有工具确实不可用时才提供提示词链接。

## 文章信息图
![文章信息图](assets/article_infographic_model.png)

> 会话内存在 `imagegen` 工具时必须实际调用并生成信息图，不得以提示词替代或自行推迟。只有工具确实不可用时，才在 `assets/article_infographic_prompt.md` 中用中文保存完整生图提示词，并在译注中说明信息图待生成；若信息图需要参考论文原图，请显式写出“信息图中的 xx 图参照文中的 Fig. x ……”。

仅在 imagegen 确实不可用时，删除上方图片引用并使用以下回退说明；工具调用失败须注明信息图未完成：

```markdown
## 文章信息图
> 当前会话没有可用的 imagegen 工具，因此交付提示词版本，已保存完整生图提示词：[article_infographic_prompt.md](assets/article_infographic_prompt.md)。
```

## 要点详解

- **研究问题**：...
- **研究材料/数据/理论背景**：...
- **方法与假设**：...
- **主要发现**：...
- **验证或局限**：...
- **科学/实践启示**：...

<!-- 根据论文主题选用以上要点，删除不适用的条目，不为填模板补造内容。 -->

## 作者信息
...

## 摘要

...

![图示](assets/figure_01.png)

**<center>图 1：图题中文翻译</center>**

| 列 1 | 列 2 |
|---|---|
| ... | ... |

**<center>表 1：表题中文翻译</center>**
```

## 全文完整性验收

全文必须按原文章节和段落顺序完整翻译，保留全部论证、限定条件、数据、公式、表格细项、图题图注、附录和参考文献。不得以概述、合并压缩、略译或“见原文”代替。长文分批继续完成；有缺失内容就列出具体位置并标记未完成。交付前建立 `source/translation_coverage.md`，逐段核对源文与译文对应关系，单纯统计公式/图表数量不能证明完整。
