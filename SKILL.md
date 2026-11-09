---
name: sci-translation-pdf2md
description: "Use this skill when converting SCI/academic PDFs into Chinese Markdown, especially when the user asks for full-text translation, PDF-to-Markdown, preserving formulas/tables/figures, extracting PDF embedded images and vector drawings with crop fallback, adding article-specific opening key points, generating an article infographic or its prompt, or exporting the translation as HTML with embedded images. Trigger phrases: /翻译论文, /translate paper."
---

# SCI Translation PDF2MD

## Purpose

Convert SCI/academic PDF papers into polished Chinese Markdown. Preserve the scholarly structure, formulas, tables, citations, and figures; produce a detailed opening summary; generate an article infographic whenever imagegen is available (use a prompt-only fallback only when the tool is unavailable); and export an additional HTML version with embedded images.

## Mandatory completeness and infographic rules

- **全文翻译禁止压缩成概述。** Translate every source paragraph in order and preserve its full meaning, reasoning, qualifications, examples, quantitative results and citations. Do not omit, merge away or shorten content for convenience, length, time or token limits. Opening key points and reading reports are additional analyses; they never replace any part of the translation.
- Translate all sections and subsections, appendices, nomenclature, footnotes, figure/table captions and notes, acknowledgments, declarations, data availability and references. Preserve every equation and its original number, every table row/column/cell, and every figure/panel. Do not relabel or renumber extracted figures by extraction order; map them to their actual source captions. Bibliographic author names, journal names and DOI identifiers may retain their original forms, but do not omit reference entries or substitute “see original PDF”.
- If the work exceeds one response or context window, split the work into sequential translation batches, retain progress, and continue until the source is covered. Never substitute a summary for unfinished sections. If source content is missing or unreadable, identify its exact location and mark it unresolved; do not invent it or declare the full translation complete.
- **If an imagegen image-generation tool is available in the current session, calling it and delivering the generated article infographic is mandatory.** Tool discovery may be needed for deferred tools. Do not choose prompt-only delivery or defer generation merely to save time. Save the generated bitmap as `assets/article_infographic_model.png`, place it near the beginning of the Markdown, and embed it in the HTML. A prompt may also be retained, but cannot substitute for the required image.
- Prompt-only fallback is permitted only when imagegen is genuinely unavailable. If an available tool fails, report the failure and the infographic as incomplete; a prompt alone does not satisfy the generated-image requirement. Continue all unaffected translation work without pretending the missing image was completed.

## Model Requirement

Use GPT-5.6 Sol (`gpt-5.6-sol`) or a newer GPT model with medium or higher reasoning effort, or a model of comparable intelligence, to carry out this skill, including visual extraction and figure-crop review. This is a requirement for the executing assistant; generated bitmap images still use the image-generation tool.

## Trigger Phrases

- `/翻译论文`
- `/translate paper`

## Output Contract

Create one output folder per paper, named with the pattern `<first_author_surname>_<Chinese_title>_中文翻译`, or `<first_author_surname>_<year>_<Chinese_title>_中文翻译` when the year is needed for disambiguation:

```text
Wood_2005_水锤分析必不可少且简单并且高效_中文翻译/
├── Wood_2005_水锤分析必不可少且简单并且高效_中文翻译.md
├── Wood_2005_水锤分析必不可少且简单并且高效_中文翻译_图片内嵌.html
├── assets/
│   ├── article_infographic_model.png  (if generated)
│   ├── article_infographic_prompt.md  (prompt-only fallback only if imagegen is unavailable)
│   ├── figure_01.png ...
│   ├── vector/
│   └── embedded/
└── source/
    └── vector_report.json
```

Use the translated Chinese title in the folder name. Keep the author surname at the front, append the year when useful, and normalize unsafe filesystem characters to underscores.

The Markdown opening should contain, in order: Chinese title, original citation/DOI, translation note, article infographic or prompt link, article-specific key points, author information, and abstract translation.

Use [references/output-template.md](references/output-template.md) when assembling the translation. Deliver both Markdown and its image-embedded HTML rendering.

## Workflow

1. **Inspect the PDF**
   - Confirm page count, metadata, selectable text quality, formulas, tables, and figure count.
   - Use `pdftotext -layout` when available; use PyMuPDF text extraction as fallback.
   - For pure-image/scanned papers, read page previews directly with model vision and extract/translate the paper visually. For mixed PDFs, use this route on pages whose text extraction is unavailable or unreliable.

2. **Extract figures**
   - The extraction script is a helper that reduces image-search and crop-preparation work. Its boxes are candidates: the model visually checks completeness and crop boundaries, adjusts them as needed, and makes the final figure decision. Use page-preview vision when script candidates are missing or unusable.
   - First extract PDF embedded images directly.
   - Prefer direct PDF embedded images whenever they are complete Figure panels. Do not replace a complete embedded image with a rendered crop, because crop-rendered figures can reduce effective resolution.
   - Treat a direct extraction as final only when it is a complete Figure panel with axes, subfigure letters, labels, legend, and all plot marks intact.
   - If the embedded extraction is a partial panel, raster fragment, mask, logo, author portrait, or missing axes/labels/legend, use crop rendering as fallback.
   - If the figure is vector content, fragmented images, masks, or missing labels after extraction, first export the vector drawing regions and their bounding boxes with `scripts/pdf2md_assets.py`.
   - Treat those exported vector boxes as the starting point for crop refinement, and mark each as `needs_review`. Do not ask the model to guess vector rectangles from scratch when the script already exported usable ranges.
   - If the vector export shows that a page is probably a full-page vectorized text layer or otherwise too noisy to trust, set that page aside and use page-preview-based model vision to recover the figure frame as a fallback.
   - After crop rendering, visually check every cropped figure for both over-cropping and loose-cropping:
     - Over-cropping: missing subfigure letters, axis labels, tick labels, legends, arrows, captions embedded inside the figure, or outer frame lines.
     - Loose-cropping: too much surrounding body text, page header/footer, page number, unrelated captions, or adjacent tables/figures.
   - Adjust the crop box until all figure-internal content is preserved with a small margin, while excluding unrelated page content.
   - Never use whole-page screenshots as final figures unless the user explicitly asks for page facsimiles.
   - Use stable filenames: `figure_01.png`, `figure_02.png`, etc.

3. **Translate to Markdown**
   - Translate all article sections, figure captions, table captions, appendix, nomenclature, acknowledgments, data availability, and references.
   - Preserve citation names and DOI links.
   - Recreate formulas with LaTeX and keep original numbering: `\tag{1}`, `\tag{A1}`, etc.
   - Recreate tables as Markdown tables when feasible; otherwise use a cropped table image plus translated caption.
   - Insert figures near their first caption or natural discussion point.
   - Every figure title/caption and table title/caption must use the centered format `**<center>图 1：标题</center>**` or `**<center>表 1：标题</center>**`. Do not leave figure/table captions as plain paragraphs.

4. **Write article-specific opening key points**
   - Use 5-8 bullets or short paragraphs adapted to the paper's actual subject and article type. Select applicable topics such as:
     - research question and motivation;
     - study materials, experimental system, data source, or theoretical setting;
     - methods, models, and assumptions;
     - main quantitative or qualitative findings;
     - validation evidence, limitations, or uncertainty when discussed;
     - scientific, clinical, practical, or engineering implications.
   - Omit inapplicable categories. Include domain-specific topics such as parameter distributions, surrogate models, or UQ/GSA only when the paper actually addresses them; never invent content to fill a template.
   - Use concise technical Chinese; avoid vague praise.

5. **Add an article infographic or generation prompt**
   - Check whether imagegen is available in the current session. If available, generate and deliver the infographic; prompt-only delivery is not acceptable. Only when the tool is genuinely unavailable may a complete Chinese generation prompt be delivered instead.
   - Use the built-in `imagegen` tool to generate the article infographic as a complete bitmap image.
   - Do not use Python, Matplotlib, PIL, SVG drawing, canvas code, or any local script to draw the infographic as a substitute for model generation.
   - Only if the built-in `imagegen` tool is genuinely unavailable, do not replace it with Python/code drawing. Instead, write a complete model-image generation prompt in Chinese to `assets/article_infographic_prompt.md` and include it in the final response so the infographic can be generated later with `imagegen`.
   - In that fallback case, do not reference a missing `assets/article_infographic_model.png`; insert a short note near the top of the Markdown that links to `assets/article_infographic_prompt.md`.
   - The fallback prompt file should itself be written in Chinese. Keep English only where needed for bibliographic fidelity, equation symbols, figure labels such as `Fig. 3`, or exact original terminology that should not be translated.
   - The infographic prompt must include as much key article information as practical: research question, relevant system/data, core equations or methods, parameters/ranges when applicable, major results, and subject-appropriate implications. Keep the intended image text concise enough for model rendering.
   - If the infographic needs to reuse, echo, or visually reference a figure from the paper, add an explicit mapping section in the prompt. Use wording like `信息图中的“方法流程图”参照文中的 Fig. 3` or `信息图中的“误差对比曲线”参照文中的 Fig. 6(a)` and briefly explain what visual structure should be retained and what should be simplified for the infographic.
   - If multiple paper figures are referenced, write one mapping line per figure so every infographic panel has a clear source reference.
   - Do not rely on local scripts to add the final infographic text unless the user explicitly asks for deterministic post-processing.
   - Keep text short and exact; dense Chinese text may distort in generated images. If the infographic must contain Chinese text, use short phrases and ask the model to render them verbatim.
   - When an image was generated, copy the final image into `assets/article_infographic_model.png`.
   - If an image was generated, insert it near the top:

```markdown
## 文章信息图
![文章信息图](assets/article_infographic_model.png)
```

   - Recommended fallback prompt structure:

```markdown
生成一张论文信息图，用于中文译文开头。
语言：中文；图中文字尽量简短、明确。
论文信息：……
核心内容：……
版式建议：……
参考图对应（如需要）：
- 信息图中的“xx图”参照文中的 Fig. x，保留……，简化……
```

6. **Verify**
   - When imagegen is available, require the actual generated `assets/article_infographic_model.png`, its Markdown reference near the top, and its embedded HTML image. Only when imagegen is unavailable accept a complete linked `assets/article_infographic_prompt.md`; that fallback must state tool unavailability and must not reference a missing PNG. A tool failure must be reported as an incomplete infographic.
   - Do not add visual or factual review of the generated infographic as an acceptance step.
   - If `--extract-vectors` was used, check that `source/vector_report.json` exists and that vector candidates are marked `needs_review`.
   - If any page is marked `needs_model_fallback`, confirm that its figure range was recovered from page-preview/model vision rather than from the raw vector boxes.
   - For prompt-only delivery, check that `assets/article_infographic_prompt.md` exists, is written primarily in Chinese, and contains a complete prompt with the paper's key information.
   - If the fallback prompt references any source figures, check that each infographic panel is mapped explicitly with `信息图中的……参照文中的 Fig. ……`.
   - Check all Markdown image references exist.
   - Check every figure and table title/caption uses `**<center>...</center>**`.
   - Check no `page_*.png` whole-page screenshot is referenced as a final figure.
   - Check source-to-translation coverage paragraph by paragraph and section by section, including appendices and references. Keep a coverage record in `source/translation_coverage.md` that identifies source page/section/paragraph ranges and corresponding translation locations, plus any unresolved content. Counts or file existence alone do not establish completeness.
   - Compare every equation and original number, every table value/row/column/note, and every figure/caption mapping against the source. Record transcription conflicts explicitly; do not silently repair uncertain source content.
   - Check formula tags, section order, table count, and figure count against the PDF.
   - If exact formulas or figures are uncertain, state this in the translation note.

7. **Export HTML with embedded images and a heading directory**
   - After the Markdown and its local images are ready, run `scripts/export_html.py`. It calls the bundled `scripts/md2html.py` converter without opening its GUI.
   - Write `<Markdown_stem>_图片内嵌.html` beside the Markdown and deliver both files. Enable the converter’s heading directory (`include_toc=True`, already set by the wrapper). If the user has named a central archive folder for finished translations, also save one copy of each completed self-contained HTML there, preserving the descriptive filename, and verify the copy matches. Local images are embedded as base64 data URIs; formulas are converted to MathML for browser rendering.
   - Read [references/html-export.md](references/html-export.md) for the command and dependencies. Missing local images cause conversion to fail; resolve those paths and rerun. Confirm that the HTML was generated and its image sources are embedded data URIs. This checks packaging only, not infographic content.

## Script

Use `scripts/pdf2md_assets.py` for repeatable text/asset extraction:

```powershell
python .\sci-translation-pdf2md\scripts\pdf2md_assets.py `
  --pdf "paper.pdf" `
  --out-dir ".\paper_output" `
  --extract-embedded `
  --extract-vectors `
  --render-pages
```

For crop fallback, create a JSON file with Figure crop boxes and pass `--crops`:

```json
{
  "figures": [
    {"name": "figure_01", "page": 3, "box": [66, 86, 545, 454]},
    {"name": "figure_02", "page": 4, "box": [184, 86, 564, 560]}
  ]
}
```

PDF coordinates are PyMuPDF page points: `[x0, y0, x1, y1]`, with pages numbered from 1.

## Quality Bar

- Final Markdown must be a complete Chinese paper translation, not a summary, abridgment, selected translation or raw OCR dump. Do not claim completion until the source-to-translation coverage audit has passed.
- Figures must be actual Figure assets or crop-rendered Figure regions, not full pages.
- Figure and table titles must be centered with `**<center>...</center>**` for easy reading.
- Opening key points should let a researcher understand the paper's contribution before reading the full translation.
- Every translation must include a model-generated infographic whenever imagegen is available in the session. Generated infographics must use imagegen, not Python/code drawing. Only genuine tool unavailability permits the prompt-only fallback.
- When imagegen is genuinely unavailable, state this and deliver a complete Chinese `article_infographic_prompt.md`. Do not treat an optional deferral as unavailability; tool failure leaves the infographic incomplete.
- When the infographic borrows a paper figure, the prompt must explicitly say which infographic panel references which `Fig.` in the paper.
- Keep generated images and extracted figures in the project output folder, not only in temporary or Codex-generated locations.

- Deliver the Markdown and an additional HTML file with embedded images, produced by the bundled converter.
