from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

CM_TO_PT = 72 / 2.54


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value).strip("_")


def rect_to_list(rect: fitz.Rect) -> list[float]:
    return [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]


def extract_embedded(doc: fitz.Document, out_dir: Path, min_width: int, min_height: int) -> list[dict]:
    embedded_dir = out_dir / "assets" / "embedded"
    embedded_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    seen: set[tuple[int, int]] = set()

    for page_index, page in enumerate(doc, start=1):
        for image in page.get_images(full=True):
            xref = image[0]
            width, height = image[2], image[3]
            if width < min_width or height < min_height:
                continue
            key = (page_index, xref)
            if key in seen:
                continue
            seen.add(key)

            extracted = doc.extract_image(xref)
            ext = extracted.get("ext", "png")
            out_path = embedded_dir / f"embedded_p{page_index:03d}_xref{xref}.{ext}"
            out_path.write_bytes(extracted["image"])
            rects = [
                [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)]
                for rect in page.get_image_rects(xref)
            ]
            records.append(
                {
                    "page": page_index,
                    "xref": xref,
                    "width": width,
                    "height": height,
                    "file": str(out_path.relative_to(out_dir)),
                    "rects": rects,
                }
            )
    return records


def clean_vector_drawings(
    drawings: list[dict],
    page_width: float,
    page_height: float,
    min_side_pt: float,
    text_length: int,
) -> list[fitz.Rect]:
    cleaned: list[fitz.Rect] = []
    for draw in drawings:
        rect = draw["rect"]
        if rect.width < min_side_pt and rect.height < min_side_pt:
            continue
        if text_length > 500 and rect.width > page_width * 0.75 and rect.height > page_height * 0.75:
            if rect.x0 < page_width * 0.2 and rect.y0 < page_height * 0.2:
                continue
        if text_length > 500 and rect.width > page_width * 0.7 and rect.height < page_height * 0.08:
            if rect.y0 < page_height * 0.15 or rect.y0 > page_height * 0.85:
                continue
        if rect.width > page_width * 0.85 and rect.height > page_height * 0.85:
            continue
        if rect.width > page_width * 0.5 and rect.height < 5:
            continue
        if rect.height > page_height * 0.5 and rect.width < 5:
            continue
        cleaned.append(rect)
    return cleaned


def merge_bboxes(rect_list: list[fitz.Rect], threshold: float = 15) -> list[fitz.Rect]:
    rects = [fitz.Rect(r) for r in rect_list]
    changed = True
    while changed:
        changed = False
        merged: list[fitz.Rect] = []
        while rects:
            current = rects.pop(0)
            expanded = fitz.Rect(
                current.x0 - threshold,
                current.y0 - threshold,
                current.x1 + threshold,
                current.y1 + threshold,
            )
            intersected_indices = [i for i, other in enumerate(rects) if expanded.intersects(other)]
            if intersected_indices:
                for i in sorted(intersected_indices, reverse=True):
                    other = rects.pop(i)
                    current = current | other
                rects.append(current)
                changed = True
            else:
                merged.append(current)
        rects = merged
    return rects


def classify_vector_page(merged_vectors: list[fitz.Rect], text_length: int, page_area: float) -> tuple[bool, int, float]:
    total_area = sum(rect.width * rect.height for rect in merged_vectors)
    coverage_ratio = total_area / page_area if page_area else 0.0

    if not merged_vectors:
        return False, text_length, coverage_ratio

    likely_vector_text = (
        len(merged_vectors) >= 60
        or (text_length < 80 and len(merged_vectors) >= 25 and coverage_ratio > 0.6)
        or (text_length < 20 and len(merged_vectors) >= 15 and coverage_ratio > 0.85)
    )
    return likely_vector_text, text_length, coverage_ratio


def extract_vectors(
    doc: fitz.Document,
    out_dir: Path,
    min_side_pt: float,
    merge_threshold: float,
    padding: float,
    zoom: float,
) -> dict:
    vector_dir = out_dir / "assets" / "vector"
    vector_dir.mkdir(parents=True, exist_ok=True)
    pages_report: list[dict] = []
    fallback_pages: list[int] = []

    for page_index, page in enumerate(doc, start=1):
        text_length = len(page.get_text("text", sort=True).strip())
        drawings = page.get_drawings()
        cleaned = clean_vector_drawings(drawings, page.rect.width, page.rect.height, min_side_pt, text_length)
        merged_vectors = merge_bboxes(cleaned, threshold=merge_threshold)
        page_area = page.rect.width * page.rect.height
        likely_vector_text, text_length, coverage_ratio = classify_vector_page(merged_vectors, text_length, page_area)

        page_record: dict = {
            "page": page_index,
            "vector_count": len(merged_vectors),
            "text_length": text_length,
            "coverage_ratio": round(coverage_ratio, 4),
            "needs_model_fallback": likely_vector_text,
            "items": [],
        }

        if likely_vector_text:
            page_record["note"] = "vector-like text detected; use page preview and model fallback for figure framing"
            fallback_pages.append(page_index)
            pages_report.append(page_record)
            continue

        for idx, rect in enumerate(merged_vectors, start=1):
            if rect.width < min_side_pt or rect.height < min_side_pt:
                continue

            padded_rect = fitz.Rect(
                max(0, rect.x0 - padding),
                max(0, rect.y0 - padding),
                min(page.rect.width, rect.x1 + padding),
                min(page.rect.height, rect.y1 + padding),
            )
            item: dict = {
                "name": f"vector_p{page_index:03d}_{idx:02d}",
                "box": rect_to_list(rect),
                "padded_box": rect_to_list(padded_rect),
                "needs_review": True,
            }

            if padded_rect.width > page.rect.width * 0.95 and padded_rect.height > page.rect.height * 0.95:
                item["skipped"] = True
                item["skip_reason"] = "padded box covers nearly the full page"
                page_record["items"].append(item)
                continue

            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=padded_rect, alpha=False)
                out_path = vector_dir / f"{item['name']}.png"
                pix.save(out_path)
                item["file"] = str(out_path.relative_to(out_dir))
            except Exception as exc:  # pragma: no cover - defensive reporting
                item["skipped"] = True
                item["skip_reason"] = str(exc)

            page_record["items"].append(item)

        pages_report.append(page_record)

    report = {
        "pdf": str(getattr(doc, "name", "")),
        "pages": doc.page_count,
        "fallback_pages": fallback_pages,
        "pages_report": pages_report,
    }
    report_path = out_dir / "source" / "vector_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_pages(doc: fitz.Document, out_dir: Path, zoom: float) -> None:
    pages_dir = out_dir / "source" / "page_previews"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for page_index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(pages_dir / f"page_{page_index:03d}.png")


def render_crops(doc: fitz.Document, crops_path: Path, out_dir: Path, zoom: float) -> list[dict]:
    data = json.loads(crops_path.read_text(encoding="utf-8"))
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for item in data.get("figures", []):
        name = safe_name(item["name"])
        page_no = int(item["page"])
        clip = fitz.Rect(*item["box"])
        out_path = assets_dir / f"{name}.png"
        pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        pix.save(out_path)
        records.append({"name": name, "page": page_no, "box": item["box"], "file": str(out_path.relative_to(out_dir))})
    return records


def write_text(doc: fitz.Document, out_dir: Path) -> None:
    source_dir = out_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    for page_index, page in enumerate(doc, start=1):
        chunks.append(f"\n\n===== PAGE {page_index:03d} =====\n\n")
        chunks.append(page.get_text("text", sort=True))
    (source_dir / "source_pages.txt").write_text("".join(chunks), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SCI PDF text and assets for Chinese PDF-to-Markdown translation.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--extract-embedded", action="store_true")
    parser.add_argument("--extract-vectors", action="store_true")
    parser.add_argument("--render-pages", action="store_true")
    parser.add_argument("--crops", type=Path, help="JSON crop specification for figure fallback rendering.")
    parser.add_argument("--zoom", type=float, default=4.0)
    parser.add_argument("--vector-zoom", type=float, default=2.0)
    parser.add_argument("--vector-min-side-cm", type=float, default=2.0)
    parser.add_argument("--vector-merge-threshold", type=float, default=15.0)
    parser.add_argument("--vector-padding", type=float, default=15.0)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=120)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(args.pdf)
    report: dict = {"pdf": str(args.pdf), "pages": doc.page_count}

    write_text(doc, args.out_dir)
    if args.extract_embedded:
        report["embedded_images"] = extract_embedded(doc, args.out_dir, args.min_width, args.min_height)
    if args.extract_vectors:
        vector_report = extract_vectors(
            doc,
            args.out_dir,
            min_side_pt=args.vector_min_side_cm * CM_TO_PT,
            merge_threshold=args.vector_merge_threshold,
            padding=args.vector_padding,
            zoom=args.vector_zoom,
        )
        report["vector_report"] = "source/vector_report.json"
        report["fallback_pages"] = vector_report["fallback_pages"]
    if args.render_pages:
        render_pages(doc, args.out_dir, zoom=2.0)
        report["page_previews"] = "source/page_previews"
    if args.crops:
        report["rendered_crops"] = render_crops(doc, args.crops, args.out_dir, args.zoom)

    report_path = args.out_dir / "source" / "asset_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote extraction report to {report_path}")


if __name__ == "__main__":
    main()
