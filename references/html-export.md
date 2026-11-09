# HTML export

`scripts/md2html.py` is the bundled Markdown-to-HTML converter, including its collapsible heading table of contents, equation tags and reference-style image embedding. Use `scripts/export_html.py` as its headless entry point. The wrapper explicitly enables `include_toc=True` so translated HTML includes the heading directory by default.

Resolve the script path relative to this skill's directory, not the current paper directory. In PowerShell:

```powershell
python "<skill-directory>\scripts\export_html.py" "<paper-output>\<paper-name>.md"
```

The default output is `<paper-output>\<paper-name>_图片内嵌.html`. To choose an explicit output path:

```powershell
python "<skill-directory>\scripts\export_html.py" "<paper-output>\<paper-name>.md" --output "<paper-output>\<paper-name>.html"
```

Use Python with `Markdown` (or `markdown2`), `latex2mathml`, and `tkinter` available. `tkinterdnd2` is optional and is not needed for the command-line route. If the Markdown or formula library is missing, install the required packages in the selected runtime: `python -m pip install Markdown latex2mathml`.

Images must already be local assets referenced relative to the Markdown, or existing data URIs. The converter renders Markdown first, then embeds local HTML `<img>` sources, including inline, reference-style, collapsed-reference, and shortcut-reference Markdown images. It stops on missing local files. It leaves external image URLs unchanged: use the paper package's local assets to meet the embedded-image output requirement.

Display formulas with `\tag{1}` or `\tag{A1}` retain their explicit number in a separate right-side label with parentheses; `\tag*{...}` produces a label without added parentheses. The formula body and label are converted separately to MathML so the tag command is not printed as formula text.

The HTML contains embedded CSS, images, and MathML formulas without a MathJax CDN. The formula converter's legacy argument name is `enable_mathjax`, but this implementation renders MathML. A link to an infographic prompt remains an ordinary link to the delivered prompt file; the prompt is not an image and is not embedded automatically.

Confirm the HTML file exists and its image sources are data URIs. No visual or factual review of the generated infographic is required.

Optional archive: if the user has named a central folder for finished translations (for example in their own AGENTS.md / CLAUDE.md), also save a copy of the self-contained HTML there. Keep the descriptive paper filename; create the directory if needed and preserve unrelated existing files. Verify the copied file matches the exported HTML. Without such a folder, skip this step.

Check that the HTML contains `id="mdtoc-nav"` and that its directory links resolve to heading IDs.
