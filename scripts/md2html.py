#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tkinter GUI: export Markdown to a standalone HTML with embedded images."""

from __future__ import annotations

import base64
import mimetypes
import os
import queue
import re
import threading
import ctypes
import winreg
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from tkinter import BooleanVar, StringVar, Text, Tk, filedialog, messagebox
from tkinter import ttk
from urllib.parse import unquote, urlparse

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False


MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((<[^>]+>|[^)\n]+)\)")
HTML_IMG_RE = re.compile(
    r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)(\2)",
    flags=re.IGNORECASE | re.DOTALL,
)
DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.DOTALL)
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)|\\\((.+?)\\\)", re.DOTALL)
MATH_TAG_RE = re.compile(r"\\tag\*?\{([^{}]*)\}")


class HeadingCollector(HTMLParser):
    """Find rendered headings and their opening tags without rewriting the HTML."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.line_starts = [0] + [match.end() for match in re.finditer("\n", html)]
        self.headings: list[dict[str, object]] = []
        self.used_ids: set[str] = set()
        self.current: dict[str, object] | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element_id = next((value for name, value in attrs if name == "id" and value), None)
        if element_id:
            self.used_ids.add(element_id)
        if re.fullmatch(r"h[1-6]", tag) and self.current is None:
            line, column = self.getpos()
            self.current = {
                "level": int(tag[1]), "id": element_id,
                "start": self.line_starts[line - 1] + column,
                "tag": self.get_starttag_text(), "text": [],
            }
        elif self.current is not None and tag == "img":
            alt = next((value for name, value in attrs if name == "alt"), None)
            if alt:
                self.current["text"].append(alt)

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None and tag == f'h{self.current["level"]}':
            self.headings.append(self.current)
            self.current = None


TOC_STYLE = """
    #mdtoc-layout { display: grid; grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
                    gap: 2rem; max-width: 1280px; margin: 2rem auto; padding: 0 1.2rem; }
    #mdtoc-nav { position: sticky; top: 1.5rem; align-self: start; max-height: calc(100vh - 3rem);
                 overflow-y: auto; border-right: 1px solid #8885; padding: .5rem 1rem .5rem 0; }
    #mdtoc-nav .mdtoc-header { display: flex; align-items: center; justify-content: space-between;
                             gap: .5rem; margin-bottom: .6rem; }
    #mdtoc-nav .mdtoc-title { font-weight: 700; }
    #mdtoc-nav .mdtoc-actions { display: flex; gap: .2rem; }
    #mdtoc-nav .mdtoc-actions button { border: 0; background: transparent; color: inherit;
                                      cursor: pointer; font: inherit; font-size: .8em; padding: .2rem; }
    #mdtoc-nav .mdtoc-actions button:hover { text-decoration: underline; }
    #mdtoc-nav ul { list-style: none; margin: 0; padding: 0; }
    #mdtoc-nav ul[hidden] { display: none; }
    #mdtoc-nav li { margin: .15rem 0; }
    #mdtoc-nav li > ul { margin-left: .75rem; padding-left: .45rem; border-left: 1px solid #8885; }
    #mdtoc-nav .mdtoc-row { display: flex; align-items: flex-start; }
    #mdtoc-nav .mdtoc-toggle, #mdtoc-nav .mdtoc-spacer { flex: 0 0 1.3rem; width: 1.3rem;
                                                          margin-top: .25rem; }
    #mdtoc-nav .mdtoc-toggle { border: 0; background: transparent; color: inherit;
                               cursor: pointer; font: inherit; line-height: 1.4; padding: 0; }
    #mdtoc-nav .mdtoc-toggle:hover, #mdtoc-nav .mdtoc-toggle:focus-visible { background: #8882; }
    #mdtoc-nav a { color: inherit; text-decoration: none; display: block; line-height: 1.4;
                   padding: .2rem .35rem; border-radius: .25rem; overflow-wrap: anywhere; min-width: 0; }
    #mdtoc-nav a:hover, #mdtoc-nav a:focus { background: #8882; text-decoration: underline; }
    #mdtoc-content { min-width: 0; }
    #mdtoc-content h1, #mdtoc-content h2, #mdtoc-content h3,
    #mdtoc-content h4, #mdtoc-content h5, #mdtoc-content h6 { scroll-margin-top: 1rem; }
    @media (max-width: 760px) {
      #mdtoc-layout { display: block; margin: 1rem auto; }
      #mdtoc-nav { position: static; max-height: 35vh; border-right: 0;
                   border-bottom: 1px solid #8885; padding: .5rem 0 1rem; margin-bottom: 1.5rem; }
    }
"""

TOC_SCRIPT = """<script>
(function () {
  const nav = document.getElementById('mdtoc-nav');
  if (!nav) return;
  function setExpanded(button, expanded) {
    const children = button.closest('li').querySelector(':scope > ul');
    if (!children) return;
    children.hidden = !expanded;
    button.setAttribute('aria-expanded', String(expanded));
    button.setAttribute('aria-label', (expanded ? '折叠：' : '展开：') + button.dataset.label);
    button.textContent = expanded ? '▾' : '▸';
  }
  nav.addEventListener('click', function (event) {
    const toggle = event.target.closest('.mdtoc-toggle');
    if (toggle && nav.contains(toggle)) setExpanded(toggle, toggle.getAttribute('aria-expanded') !== 'true');
  });
  nav.querySelectorAll('.mdtoc-action').forEach(function (action) {
    action.addEventListener('click', function () {
      const expanded = action.dataset.expand === 'true';
      nav.querySelectorAll('.mdtoc-toggle').forEach(function (toggle) {
        setExpanded(toggle, expanded);
      });
    });
  });
}());
</script>"""


def add_heading_toc(html: str) -> tuple[str, str | None]:
    """Add missing heading anchors and return a collapsible heading tree."""
    collector = HeadingCollector(html)
    if not collector.headings:
        return html, None
    replacements: list[tuple[int, str, str]] = []
    roots: list[dict[str, object]] = []
    stack: list[dict[str, object]] = []
    for index, heading in enumerate(collector.headings, 1):
        heading_id = heading["id"]
        if not heading_id:
            heading_id = f"mdtoc-heading-{index}"
            while heading_id in collector.used_ids:
                heading_id += "-"
            collector.used_ids.add(heading_id)
            original_tag = str(heading["tag"])
            replacement = original_tag[:-1] + f' id="{heading_id}">'
            replacements.append((int(heading["start"]), original_tag, replacement))
        label = " ".join("".join(heading["text"]).split()) or f"标题 {index}"
        level = int(heading["level"])
        node: dict[str, object] = {
            "level": level, "id": str(heading_id), "label": label, "children": [],
        }
        while stack and int(stack[-1]["level"]) >= level:
            stack.pop()
        siblings = stack[-1]["children"] if stack else roots
        siblings.append(node)
        stack.append(node)
    for start, original, replacement in reversed(replacements):
        html = html[:start] + replacement + html[start + len(original):]
    def render_nodes(nodes: list[dict[str, object]]) -> str:
        items = []
        for node in nodes:
            label = escape(str(node["label"]))
            link = f'<a href="#{escape(str(node["id"]), quote=True)}">{label}</a>'
            children = node["children"]
            if children:
                toggle = (
                    f'<button type="button" class="mdtoc-toggle" aria-expanded="true" '
                    f'aria-label="折叠：{escape(str(node["label"]), quote=True)}" '
                    f'data-label="{escape(str(node["label"]), quote=True)}">▾</button>'
                )
                subtree = f"<ul>{render_nodes(children)}</ul>"
            else:
                toggle = '<span class="mdtoc-spacer" aria-hidden="true"></span>'
                subtree = ""
            items.append(f'<li><div class="mdtoc-row">{toggle}{link}</div>{subtree}</li>')
        return "".join(items)

    nav = (
        '<nav id="mdtoc-nav" aria-label="文章目录">'
        '<div class="mdtoc-header"><span class="mdtoc-title">目录</span>'
        '<span class="mdtoc-actions">'
        '<button type="button" class="mdtoc-action" data-expand="true">全部展开</button>'
        '<button type="button" class="mdtoc-action" data-expand="false">全部折叠</button>'
        '</span></div><ul class="mdtoc-tree">'
    )
    return html, nav + render_nodes(roots) + "</ul></nav>"


def add_toc_to_existing_html(html: str) -> str:
    html, nav = add_heading_toc(html)
    if nav is None:
        return html
    body_open = re.search(r"<body\b[^>]*>", html, flags=re.IGNORECASE)
    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    if not body_open or not body_close or body_close.start() < body_open.end():
        return build_html(html, "HTML 文档", toc_nav=nav)
    html = (
        html[:body_open.end()] + '<div id="mdtoc-layout">' + nav
        + '<main id="mdtoc-content">' + html[body_open.end():body_close.start()]
        + "</main></div>" + html[body_close.start():]
    )
    head_close = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if head_close:
        html = html[:head_close.start()] + f"<style>{TOC_STYLE}</style>\n" + html[head_close.start():]
    else:
        html = re.sub(r"(<body\b)", f"<style>{TOC_STYLE}</style>\n\\1", html, count=1, flags=re.IGNORECASE)
    body_close = re.search(r"</body\s*>", html, flags=re.IGNORECASE)
    return html[:body_close.start()] + TOC_SCRIPT + "\n" + html[body_close.start():]


def is_external(src: str) -> bool:
    value = src.strip().lower()
    return not value or value.startswith(
        ("data:", "http://", "https://", "//", "cid:", "#")
    )


def clean_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    if " \"" in value or " '" in value:
        value = re.split(r"\s+[\"']", value, maxsplit=1)[0]
    return value.strip()


def resolve_local(src: str, base_dir: Path) -> Path:
    value = unquote(src.strip())
    if value.lower().startswith("file://"):
        parsed = urlparse(value)
        value = unquote(parsed.path)
        if parsed.netloc:
            value = f"//{parsed.netloc}{value}"
    value = value.split("?", 1)[0].split("#", 1)[0]
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def to_data_uri(src: str, base_dir: Path) -> tuple[str | None, str | None]:
    if is_external(src):
        return None, None
    path = resolve_local(src, base_dir)
    if not path.is_file():
        return None, str(path)
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}", None


def embed_images(text: str, base_dir: Path) -> tuple[str, list[str], int]:
    missing: list[str] = []
    embedded_count = 0

    def replace_markdown(match: re.Match[str]) -> str:
        nonlocal embedded_count
        alt, raw_dest = match.groups()
        dest = clean_destination(raw_dest)
        uri, missing_path = to_data_uri(dest, base_dir)
        if missing_path:
            missing.append(f"{dest} → {missing_path}")
            return match.group(0)
        if uri is None:
            return match.group(0)
        embedded_count += 1
        return f"![{alt}]({uri})"

    result = MD_IMAGE_RE.sub(replace_markdown, text)

    def replace_html(match: re.Match[str]) -> str:
        nonlocal embedded_count
        prefix, quote, src, closing_quote = match.groups()
        uri, missing_path = to_data_uri(src, base_dir)
        if missing_path:
            missing.append(f"{src} → {missing_path}")
            return match.group(0)
        if uri is None:
            return match.group(0)
        embedded_count += 1
        return f"{prefix}{quote}{uri}{closing_quote}"

    result = HTML_IMG_RE.sub(replace_html, result)
    return result, missing, embedded_count


def render_markdown(text: str) -> str:
    try:
        import markdown

        return markdown.markdown(
            text,
            extensions=["extra", "fenced_code", "tables", "sane_lists", "toc"],
            output_format="html5",
        )
    except ImportError:
        try:
            import markdown2

            return markdown2.markdown(text, extras=["fenced-code-blocks", "tables"])
        except ImportError as exc:
            raise RuntimeError(
                "未安装 Markdown 转换库。请安装 Python-Markdown：\n"
                "python -m pip install Markdown"
            ) from exc

def embed_html_images(text: str, base_dir: Path) -> tuple[str, list[str], int]:
    missing=[]; count=0
    def repl(m):
        nonlocal count
        prefix, quote, src, closing = m.groups()
        uri, miss = to_data_uri(src, base_dir)
        if miss:
            missing.append(f"{src} → {miss}"); return m.group(0)
        if uri is None: return m.group(0)
        count += 1
        return f"{prefix}{quote}{uri}{closing}"
    return HTML_IMG_RE.sub(repl, text), missing, count


def render_latex_math(text: str) -> str:
    """Pre-render LaTeX to offline MathML, including display equation tags."""
    try:
        from latex2mathml.converter import convert as latex_to_mathml
    except ImportError as exc:
        raise RuntimeError(
            "缺少公式转换库 latex2mathml。请安装：python -m pip install latex2mathml"
        ) from exc

    placeholders: dict[str, str] = {}

    def make(source: str, display: bool) -> str:
        source = source.strip()
        tag = ""
        if display:
            match = MATH_TAG_RE.search(source)
            if match:
                tag = match.group(1).strip()
                source = MATH_TAG_RE.sub("", source)
        source = re.sub(r"\\arg\b", r"\\operatorname{arg}", source)
        try:
            mathml = latex_to_mathml(source, display="block" if display else "inline")
        except Exception:
            return f'<code class="latex-unparsed">{escape(source)}</code>'
        return (
            f'<div class="math-display"><span class="math-body">{mathml}</span>'
            + (f'<span class="math-tag">({escape(tag)})</span>' if tag else "")
            + '</div>'
            if display
            else f'<span class="math-inline">{mathml}</span>'
        )

    def replace_display(match: re.Match[str]) -> str:
        source = match.group(1) if match.group(1) is not None else match.group(2)
        key = f"MATHPLACEHOLDER{len(placeholders)}ENDMATH"
        placeholders[key] = make(source, True)
        return key

    def replace_inline(match: re.Match[str]) -> str:
        source = match.group(1) if match.group(1) is not None else match.group(2)
        key = f"MATHPLACEHOLDER{len(placeholders)}ENDMATH"
        placeholders[key] = make(source, False)
        return key

    result = DISPLAY_MATH_RE.sub(replace_display, text)
    result = INLINE_MATH_RE.sub(replace_inline, result)
    return result, placeholders


def build_html(
    body: str, title: str, enable_mathjax: bool = True, toc_nav: str | None = None
) -> str:
    if toc_nav:
        body = f'<div id="mdtoc-layout">{toc_nav}<main id="mdtoc-content">{body}</main></div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ max-width: {"none" if toc_nav else "960px"};
            margin: {"0" if toc_nav else "2rem auto"};
            padding: {"0" if toc_nav else "0 1.2rem"};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
            line-height: 1.75; }}
    img {{ max-width: 100%; height: auto; display: block; margin: 1rem auto; }}
    .math-display {{ position: relative; text-align: center; margin: 1.2rem 0; }}
    .math-body {{ display: inline-block; max-width: calc(100% - 4rem); vertical-align: middle;
                  overflow-x: auto; overflow-y: hidden; }}
    .math-tag {{ position: absolute; right: 0; top: 50%; transform: translateY(-50%); }}
    .math-inline {{ white-space: nowrap; }}
    .math-display math, .math-inline math {{ font-size: 1.08em; }}
    .latex-unparsed {{ color: #b42318; background: #fff1f0; padding: .1rem .25rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #8888; padding: .45rem .65rem; }}
    th {{ background: #8882; }}
    pre {{ overflow-x: auto; padding: 1rem; border-radius: .4rem; background: #8882; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
    blockquote {{ border-left: .25rem solid #8888; margin-left: 0; padding-left: 1rem; }}
    {TOC_STYLE if toc_nav else ""}
  </style>
</head>
<body>
{body}
{TOC_SCRIPT if toc_nav else ""}
</body>
</html>
"""


def convert(
    source: Path,
    output: Path,
    fail_on_missing: bool,
    enable_mathjax: bool = True,
    include_toc: bool = False,
) -> tuple[int, list[str]]:
    markdown_text = source.read_text(encoding="utf-8-sig")
    if source.suffix.lower() in {".html", ".htm"}:
        return convert_html_text(markdown_text, output, source.parent, fail_on_missing, include_toc)
    return convert_markdown_text(
        markdown_text, output, source.parent, source.stem,
        fail_on_missing=fail_on_missing, enable_mathjax=enable_mathjax,
        include_toc=include_toc,
    )


def convert_markdown_text(
    markdown_text: str,
    output: Path,
    base_dir: Path,
    title: str,
    fail_on_missing: bool = False,
    enable_mathjax: bool = True,
    include_toc: bool = False,
) -> tuple[int, list[str]]:
    embedded_text, missing, count = embed_images(markdown_text, base_dir)
    if missing and fail_on_missing:
        raise RuntimeError("发现找不到的本地图片：\n" + "\n".join(missing))
    math_text, placeholders = render_latex_math(embedded_text) if enable_mathjax else (embedded_text, {})
    body = render_markdown(math_text)
    for key, rendered in placeholders.items():
        body = body.replace(f"<p>{key}</p>", rendered)
        body = body.replace(key, rendered)
    toc_nav = None
    if include_toc:
        body, toc_nav = add_heading_toc(body)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_html(body, title, enable_mathjax=enable_mathjax, toc_nav=toc_nav), encoding="utf-8"
    )
    return count, missing


def convert_html_text(
    html_text: str, output: Path, base_dir: Path, fail_on_missing: bool = False,
    include_toc: bool = False,
) -> tuple[int, list[str]]:
    result, missing, count = embed_html_images(html_text, base_dir)
    if missing and fail_on_missing:
        raise RuntimeError("发现缺失图片：\n" + "\n".join(missing))
    if include_toc:
        result = add_toc_to_existing_html(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    return count, missing


def default_output_path() -> Path:
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            desktop = Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))
    except (OSError, ValueError):
        desktop = Path.home() / "Desktop"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return desktop / f"{stamp}.html"


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Markdown 转 HTML")
        self.root.geometry("900x650")
        self.root.minsize(760, 520)

        self.output_var = StringVar()
        self.input_var = StringVar(value="拖入 MD / HTML 文件，或点击右侧选择（可选）")
        self.status_var = StringVar(value="就绪")
        self.include_toc_var = BooleanVar(value=True)
        self.source_path: Path | None = None
        self.source_format = "markdown"
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self.root.after(120, self._poll_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except Exception:
            style.theme_use("clam")

        main = ttk.Frame(self.root, padding=18)
        self.main = main
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        editor_frame = ttk.Frame(main)
        self.editor_frame = editor_frame
        editor_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 16))
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)
        self.editor = Text(
            editor_frame, font=("Consolas", 11), wrap="word", undo=True,
            padx=12, pady=12, relief="solid", borderwidth=1,
            background="#ffffff", foreground="#212529", insertbackground="#212529",
            selectbackground="#cfe2ff",
        )
        self.editor.grid(row=0, column=0, sticky="nsew")
        editor_scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self.editor.yview)
        editor_scroll.grid(row=0, column=1, sticky="ns")
        self.editor.configure(yscrollcommand=editor_scroll.set)
        if DND_AVAILABLE:
            self.editor.drop_target_register(DND_FILES)
            self.editor.dnd_bind("<<Drop>>", self._on_drop)

        input_row = ttk.Frame(main)
        self.input_row = input_row
        input_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        input_row.columnconfigure(1, weight=1)
        ttk.Label(input_row, text="输入文件（MD / HTML）", width=20).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.input_entry = ttk.Entry(
            input_row, textvariable=self.input_var, state="readonly"
        )
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            input_row, text="选择…", command=self.choose_input, width=13
        ).grid(row=0, column=2)
        if DND_AVAILABLE:
            self.input_entry.drop_target_register(DND_FILES)
            self.input_entry.dnd_bind("<<Drop>>", self._on_drop)

        output_row = ttk.Frame(main)
        self.output_row = output_row
        output_row.grid(row=2, column=0, sticky="ew")
        output_row.columnconfigure(1, weight=1)
        ttk.Label(output_row, text="输出 HTML 文件", width=20).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Entry(output_row, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            output_row, text="选择…", command=self.choose_output, width=13
        ).grid(row=0, column=2)

        ttk.Checkbutton(
            main, text="导出侧边目录（按标题层级生成）", variable=self.include_toc_var
        ).grid(row=3, column=0, sticky="w", pady=(12, 0))

        footer = ttk.Frame(main)
        footer.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer, textvariable=self.status_var
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.folder_button = ttk.Button(
            footer, text="打开文件夹", command=self.open_output_folder, width=13
        )
        self.folder_button.grid(row=0, column=1, padx=(0, 8))
        self.export_button = ttk.Button(
            footer, text="开始导出", command=self.start_export, width=13
        )
        self.export_button.grid(row=0, column=2, sticky="e")
    def choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 Markdown 或 HTML 文件",
            filetypes=[("Markdown / HTML", "*.md *.markdown *.html *.htm"), ("所有文件", "*.*")],
        )
        if path:
            self._load_input_file(Path(path))

    def _load_input_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("读取失败", f"无法读取文件：\n{path}\n\n{exc}")
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.source_path = path
        self.input_var.set(str(path))
        self.source_format = "html" if path.suffix.lower() in {".html", ".htm"} else "markdown"
        self.output_var.set(
            str(path.with_name(f"{path.stem}_图片内嵌.html"))
            if self.source_format == "html" else str(path.with_suffix(".html"))
        )
        self.status_var.set("已导入文件")

    def _on_drop(self, event: object) -> str:
        paths = self.root.tk.splitlist(getattr(event, "data", ""))
        files = [Path(p) for p in paths if p]
        allowed = [p for p in files if p.is_file() and p.suffix.lower() in {".md", ".markdown", ".html", ".htm"}]
        if allowed:
            self._load_input_file(allowed[0])
        else:
            self.status_var.set("仅支持 .md、.markdown、.html 或 .htm 文件")
        return "break"

    def choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="选择 HTML 输出位置",
            defaultextension=".html",
            filetypes=[("HTML 文件", "*.html"), ("所有文件", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def open_output_folder(self) -> None:
        output_text = self.output_var.get().strip()
        folder = (
            Path(output_text).expanduser().parent
            if output_text else
            self.source_path.parent if self.source_path else default_output_path().parent
        )
        if not folder.is_dir():
            messagebox.showerror("文件夹不存在", f"找不到文件夹：\n{folder}")
            return
        try:
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror("打开失败", f"无法打开文件夹：\n{folder}\n\n{exc}")

    def start_export(self) -> None:
        content = self.editor.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("缺少内容", "请先输入 Markdown 文本或导入文件。")
            self.editor.focus_set()
            return

        output_text = self.output_var.get().strip()
        if not output_text:
            output_text = str(default_output_path())
            self.output_var.set(output_text)
        output = Path(output_text).expanduser()
        if self.source_path and self.source_path.resolve() == output.resolve():
            messagebox.showerror("输出位置无效", "输出文件不能覆盖导入文件。")
            return

        self.export_button.configure(state="disabled")
        self.status_var.set("正在转换…")
        base_dir = self.source_path.parent if self.source_path else output.parent
        threading.Thread(
            target=self._worker,
            args=(content, self.source_format, output, base_dir, self.include_toc_var.get()),
            daemon=True,
        ).start()

    def _worker(
        self, content: str, source_format: str, output: Path, base_dir: Path, include_toc: bool
    ) -> None:
        try:
            if source_format == "html":
                count, missing = convert_html_text(content, output, base_dir, include_toc=include_toc)
            else:
                count, missing = convert_markdown_text(
                    content, output, base_dir, output.stem, include_toc=include_toc
                )
            self.events.put(("success", (output, count, missing)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self.export_button.configure(state="normal")
                if kind == "success":
                    output, count, missing = payload
                    self.status_var.set(
                        f"导出完成 · 内嵌图片 {count} 个"
                        + (f" · 未找到 {len(missing)} 个图片（保留原路径）" if missing else "")
                    )
                else:
                    self.status_var.set("导出失败")
                    messagebox.showerror("导出失败", str(payload))
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    root = TkinterDnD.Tk() if DND_AVAILABLE else Tk()
    try:
        root.tk.call("tk", "scaling", max(1.0, root.winfo_fpixels("1i") / 72.0))
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
