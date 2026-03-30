from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
RAW_DIR = ROOT / "outputs" / "docai_raw" / "form"
PRED_DIR = ROOT / "outputs" / "pred"
OUT_FILE = PRED_DIR / "pred_docai_form_sample30.json"

# 與 GT 對齊
# 0 Picture
# 1 Section-header
# 2 Table
# 3 Text
# 4 Title
TABLE_CATEGORY_ID = 2
TEXT_CATEGORY_ID = 3

DEFAULT_SCORE = 0.99


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_vertices_from_bounding_poly(
    bounding_poly: dict,
    image_width: float,
    image_height: float,
) -> list[tuple[float, float]]:
    """
    Document AI 可能提供：
    - vertices: 絕對座標
    - normalized_vertices: 相對座標 (0~1)

    優先用 vertices，沒有再 fallback normalized_vertices。
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
            out.append((float(x), float(y)))
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
            out.append((float(x) * image_width, float(y) * image_height))
        if out:
            return out

    return []


def polygon_to_coco_bbox(vertices: list[tuple[float, float]]) -> list[float] | None:
    if not vertices:
        return None

    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]

    x_min = min(xs)
    y_min = min(ys)
    x_max = max(xs)
    y_max = max(ys)

    w = max(x_max - x_min, 1.0)
    h = max(y_max - y_min, 1.0)

    return [round(x_min, 2), round(y_min, 2), round(w, 2), round(h, 2)]


def get_page_size(page: dict, fallback_width: float, fallback_height: float) -> tuple[float, float]:
    dim = page.get("dimension", {})

    width = dim.get("width")
    height = dim.get("height")

    try:
        w = float(width)
    except (TypeError, ValueError):
        w = float(fallback_width)

    try:
        h = float(height)
    except (TypeError, ValueError):
        h = float(fallback_height)

    return w, h


def get_layout_bbox(
    node: dict,
    image_width: float,
    image_height: float,
) -> list[float] | None:
    """
    Page-level element 常見格式：
    node["layout"]["bounding_poly"]
    """
    if not isinstance(node, dict):
        return None

    layout = node.get("layout")
    if not isinstance(layout, dict):
        return None

    bounding_poly = layout.get("bounding_poly")
    if not isinstance(bounding_poly, dict):
        return None

    vertices = get_vertices_from_bounding_poly(
        bounding_poly=bounding_poly,
        image_width=image_width,
        image_height=image_height,
    )
    return polygon_to_coco_bbox(vertices)


def collect_page_items(page: dict, key: str) -> list[dict]:
    items = page.get(key, [])
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not RAW_DIR.exists():
        raise SystemExit(f"DocAI FORM raw dir not found: {RAW_DIR}")

    PRED_DIR.mkdir(parents=True, exist_ok=True)

    gt = load_json(GT_FILE)
    gt_images = gt["images"]

    image_id_to_info = {img["id"]: img for img in gt_images}
    stem_to_image_id = {Path(img["file_name"]).stem: img["id"] for img in gt_images}

    preds = []

    mapped_counter = Counter()
    no_bbox_counter = Counter()
    skipped_counter = Counter()
    file_pred_counter = Counter()

    json_paths = sorted(RAW_DIR.glob("*.json"))

    for json_path in json_paths:
        stem = json_path.stem

        # 只處理 GT 裡面有的 sample，避免掃到多餘檔案
        if stem not in stem_to_image_id:
            skipped_counter["not_in_gt"] += 1
            continue

        image_id = stem_to_image_id[stem]
        gt_img_info = image_id_to_info[image_id]

        doc = load_json(json_path)

        pages = doc.get("pages", [])
        if not isinstance(pages, list) or not pages:
            skipped_counter["no_pages"] += 1
            continue

        page = pages[0]
        if not isinstance(page, dict):
            skipped_counter["page0_not_dict"] += 1
            continue

        image_width, image_height = get_page_size(
            page=page,
            fallback_width=float(gt_img_info["width"]),
            fallback_height=float(gt_img_info["height"]),
        )

        # -------------------------------------------------
        # 1) blocks -> Text
        # -------------------------------------------------
        blocks = collect_page_items(page, "blocks")
        for block in blocks:
            coco_bbox = get_layout_bbox(
                node=block,
                image_width=image_width,
                image_height=image_height,
            )
            if coco_bbox is None:
                no_bbox_counter["blocks"] += 1
                continue

            preds.append({
                "image_id": image_id,
                "category_id": TEXT_CATEGORY_ID,
                "bbox": coco_bbox,
                "score": DEFAULT_SCORE,
            })
            mapped_counter["Text"] += 1
            file_pred_counter[stem] += 1

        # -------------------------------------------------
        # 2) tables -> Table
        # -------------------------------------------------
        tables = collect_page_items(page, "tables")
        for table in tables:
            coco_bbox = get_layout_bbox(
                node=table,
                image_width=image_width,
                image_height=image_height,
            )
            if coco_bbox is None:
                no_bbox_counter["tables"] += 1
                continue

            preds.append({
                "image_id": image_id,
                "category_id": TABLE_CATEGORY_ID,
                "bbox": coco_bbox,
                "score": DEFAULT_SCORE,
            })
            mapped_counter["Table"] += 1
            file_pred_counter[stem] += 1

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_predictions: {len(preds)}")

    print("\n[INFO] mapped categories")
    for label, count in mapped_counter.most_common():
        print(f"  {label}: {count}")
    if not mapped_counter:
        print("  (none)")

    print("\n[INFO] items with no usable bbox")
    for label, count in no_bbox_counter.most_common():
        print(f"  {label}: {count}")
    if not no_bbox_counter:
        print("  (none)")

    print("\n[INFO] skipped files")
    for label, count in skipped_counter.most_common():
        print(f"  {label}: {count}")
    if not skipped_counter:
        print("  (none)")

    print("\n[INFO] predictions per file")

    def sort_key(item: tuple[str, int]):
        stem = item[0]
        return (0, int(stem)) if stem.isdigit() else (1, stem)

    for stem, count in sorted(file_pred_counter.items(), key=sort_key):
        print(f"  {stem}: {count}")


if __name__ == "__main__":
    main()