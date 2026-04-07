from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "docai_raw" / "form"

# 輸出目錄：專門放從 doc_form processor 抽出的表格
OUT_DIR = ROOT / "outputs" / "docform_table"
OUT_JSON_DIR = OUT_DIR / "json"
OUT_MD_DIR = OUT_DIR / "md"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_text_from_layout(layout: dict, full_text: str) -> str:
    """
    從 Document AI 的 layout.text_anchor.text_segments
    回推出對應文字。
    """
    if not isinstance(layout, dict):
        return ""

    text_anchor = layout.get("text_anchor")
    if not isinstance(text_anchor, dict):
        return ""

    text_segments = text_anchor.get("text_segments")
    if not isinstance(text_segments, list):
        return ""

    parts: list[str] = []

    for seg in text_segments:
        if not isinstance(seg, dict):
            continue

        start = int(seg.get("start_index", 0))
        end = seg.get("end_index")
        if end is None:
            continue

        end = int(end)
        parts.append(full_text[start:end])

    text = "".join(parts)
    text = text.replace("\u00a0", " ")
    return text.strip()


def get_vertices_from_bounding_poly(
    bounding_poly: dict,
    image_width: float,
    image_height: float,
) -> list[dict]:
    """
    回傳標準化後的 vertices，方便後續一起存。
    若原本是 normalized_vertices 就轉成 absolute。
    """
    vertices = bounding_poly.get("vertices")
    if isinstance(vertices, list) and vertices:
        out = []
        for pt in vertices:
            if not isinstance(pt, dict):
                continue
            x = pt.get("x")
            y = pt.get("y")
            if x is None or y is None:
                continue
            out.append({"x": float(x), "y": float(y)})
        if out:
            return out

    normalized_vertices = bounding_poly.get("normalized_vertices")
    if isinstance(normalized_vertices, list) and normalized_vertices:
        out = []
        for pt in normalized_vertices:
            if not isinstance(pt, dict):
                continue
            x = pt.get("x")
            y = pt.get("y")
            if x is None or y is None:
                continue
            out.append({
                "x": float(x) * image_width,
                "y": float(y) * image_height,
            })
        if out:
            return out

    return []


def get_layout_bbox_and_vertices(
    node: dict,
    image_width: float,
    image_height: float,
) -> tuple[list[float] | None, list[dict]]:
    """
    從 node["layout"]["bounding_poly"] 取 bbox 與 vertices
    """
    if not isinstance(node, dict):
        return None, []

    layout = node.get("layout")
    if not isinstance(layout, dict):
        return None, []

    bounding_poly = layout.get("bounding_poly")
    if not isinstance(bounding_poly, dict):
        return None, []

    vertices = get_vertices_from_bounding_poly(
        bounding_poly=bounding_poly,
        image_width=image_width,
        image_height=image_height,
    )
    if not vertices:
        return None, []

    xs = [p["x"] for p in vertices]
    ys = [p["y"] for p in vertices]

    x_min = min(xs)
    y_min = min(ys)
    x_max = max(xs)
    y_max = max(ys)

    bbox = [
        round(x_min, 2),
        round(y_min, 2),
        round(max(x_max - x_min, 1.0), 2),
        round(max(y_max - y_min, 1.0), 2),
    ]
    return bbox, vertices


def get_page_size(page: dict) -> tuple[float, float]:
    dim = page.get("dimension", {})
    width = dim.get("width", 0)
    height = dim.get("height", 0)

    try:
        w = float(width)
    except (TypeError, ValueError):
        w = 0.0

    try:
        h = float(height)
    except (TypeError, ValueError):
        h = 0.0

    return w, h


def normalize_cell_text(text: str) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return text.strip()


def extract_table_rows(
    table: dict,
    full_text: str,
) -> tuple[list[list[str]], list[list[str]]]:
    """
    回傳:
    - header_rows
    - body_rows
    每列都是 list[str]
    """
    def parse_rows(row_items: Any) -> list[list[str]]:
        out: list[list[str]] = []

        if not isinstance(row_items, list):
            return out

        for row in row_items:
            if not isinstance(row, dict):
                continue

            cells = row.get("cells", [])
            if not isinstance(cells, list):
                out.append([])
                continue

            cell_texts: list[str] = []
            for cell in cells:
                if not isinstance(cell, dict):
                    cell_texts.append("")
                    continue

                layout = cell.get("layout", {})
                text = get_text_from_layout(layout, full_text)
                cell_texts.append(normalize_cell_text(text))

            out.append(cell_texts)

        return out

    header_rows = parse_rows(table.get("header_rows", []))
    body_rows = parse_rows(table.get("body_rows", []))
    return header_rows, body_rows


def rows_to_markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return "_Empty table_"

    max_cols = max(len(r) for r in rows) if rows else 0
    if max_cols == 0:
        return "_Empty table_"

    padded_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    header = padded_rows[0]
    body = padded_rows[1:]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def build_table_json(
    table: dict,
    table_index: int,
    page_index: int,
    image_width: float,
    image_height: float,
    full_text: str,
) -> dict:
    bbox, vertices = get_layout_bbox_and_vertices(
        node=table,
        image_width=image_width,
        image_height=image_height,
    )

    header_rows, body_rows = extract_table_rows(table, full_text)
    all_rows = header_rows + body_rows

    return {
        "table_index": table_index,
        "page_index": page_index,
        "bbox": bbox,
        "vertices": vertices,
        "header_rows": header_rows,
        "body_rows": body_rows,
        "markdown": rows_to_markdown_table(all_rows),
    }


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"RAW_DIR not found: {RAW_DIR}")

    OUT_JSON_DIR.mkdir(parents=True, exist_ok=True)
    OUT_MD_DIR.mkdir(parents=True, exist_ok=True)

    json_paths = sorted(RAW_DIR.glob("*.json"))
    if not json_paths:
        raise SystemExit(f"No json files found in: {RAW_DIR}")

    total_files = 0
    total_tables = 0
    files_with_tables = 0

    for json_path in json_paths:
        stem = json_path.stem
        doc = load_json(json_path)

        full_text = doc.get("text", "")
        pages = doc.get("pages", [])

        if not isinstance(pages, list) or not pages:
            print(f"[WARN] skip {json_path.name}: no pages")
            continue

        extracted_tables: list[dict] = []

        for page_idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue

            image_width, image_height = get_page_size(page)
            tables = page.get("tables", [])

            if not isinstance(tables, list):
                continue

            for table_idx, table in enumerate(tables, start=1):
                if not isinstance(table, dict):
                    continue

                extracted = build_table_json(
                    table=table,
                    table_index=table_idx,
                    page_index=page_idx,
                    image_width=image_width,
                    image_height=image_height,
                    full_text=full_text,
                )
                extracted_tables.append(extracted)

        # 1) 每個檔案輸出一份只保留 table 的 json
        out_json = {
            "source_file": json_path.name,
            "source_processor": "docai_form",
            "num_tables": len(extracted_tables),
            "tables": extracted_tables,
        }
        save_json(OUT_JSON_DIR / f"{stem}_tables.json", out_json)

        # 2) 每個檔案輸出一份 md，把所有表格可視化
        md_lines: list[str] = []
        md_lines.append(f"# Tables extracted from {json_path.name}")
        md_lines.append("")
        md_lines.append(f"- source_processor: docai_form")
        md_lines.append(f"- num_tables: {len(extracted_tables)}")
        md_lines.append("")

        if not extracted_tables:
            md_lines.append("_No tables found._")
        else:
            for t in extracted_tables:
                md_lines.append(f"## Table {t['table_index']} (page {t['page_index'] + 1})")
                md_lines.append("")
                if t["bbox"] is not None:
                    md_lines.append(f"- bbox: {t['bbox']}")
                    md_lines.append("")
                md_lines.append(t["markdown"])
                md_lines.append("")

        md_path = OUT_MD_DIR / f"{stem}_tables.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        total_files += 1
        total_tables += len(extracted_tables)
        if extracted_tables:
            files_with_tables += 1

        print(
            f"[OK] {json_path.name} -> "
            f"{len(extracted_tables)} table(s), "
            f"json: {stem}_tables.json, md: {stem}_tables.md"
        )

    print("\n[SUMMARY]")
    print(f"  processed files   : {total_files}")
    print(f"  files with tables : {files_with_tables}")
    print(f"  total tables      : {total_tables}")
    print(f"  out json dir      : {OUT_JSON_DIR}")
    print(f"  out md dir        : {OUT_MD_DIR}")


if __name__ == "__main__":
    main()