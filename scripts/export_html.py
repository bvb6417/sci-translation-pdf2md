"""Headless entry point for the bundled md2html converter."""
from __future__ import annotations

import argparse
from pathlib import Path

from md2html import convert


def main() -> None:
    parser = argparse.ArgumentParser(description='Export Markdown with embedded local images and MathML formulas.')
    parser.add_argument('source', type=Path, help='Input Markdown file')
    parser.add_argument('--output', type=Path, help='Default: <source_stem>_图片内嵌.html beside the source')
    args = parser.parse_args()
    source = args.source.resolve()
    output = (args.output or source.with_name(source.stem + '_图片内嵌.html')).resolve()
    if not source.is_file() or source.suffix.lower() not in {'.md', '.markdown'}:
        parser.error('source must be an existing Markdown file')
    if output == source or output.suffix.lower() not in {'.html', '.htm'}:
        parser.error('output must be a separate HTML file')
    try:
        count, _ = convert(source, output, fail_on_missing=True, enable_mathjax=True, include_toc=True)
    except Exception as exc:
        parser.exit(1, f'HTML export failed: {exc}\n')
    print(f'Wrote {output}; embedded {count} local images.')


if __name__ == '__main__':
    main()
