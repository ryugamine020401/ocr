from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
RAW_DIR = ROOT / "outputs" / "docai_raw" / "layout"
PRED_DIR = ROOT / "outputs" / "pred"
OUT_FILE = PRED_DIR / "pred_docai_layout_sample30.json"

# 與 GT 對齊
# 0 Picture
# 1 Section-header
# 2 Table
# 3 Text
# 4 Title
SECTION_HEADER_CATEGORY_ID = 1
TABLE_CATEGORY_ID = 2
TEXT_CATEGORY_ID = 3
TITLE_CATEGORY_ID = 4

DEFAULT_SCORE = 0.99


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def get_vertices_from_bounding_poly(
    bounding_poly: dict,
    image_width: float,
    image_height: float,
) -> list[tuple[float, float]]:
    """
    支援兩種格式：
    - vertices: 絕對座標
    - normalized_vertices: 0~1 相對座標
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


def get_page_size_from_gt(gt_img_info: dict) -> tuple[float, float]:
    return float(gt_img_info["width"]), float(gt_img_info["height"])


def find_first_bbox_recursively(
    node: Any,
    image_width: float,
    image_height: float,
    max_depth: int = 12,
) -> list[float] | None:
    """
    針對 layout processor:
    我們不假設 bbox 一定在哪個固定 path，
    而是遞迴搜尋常見幾何欄位。

    搜尋順序：
    1. bounding_poly
    2. bbox = [x1,y1,x2,y2] 或 [x,y,w,h]
    3. vertices / normalized_vertices
    4. layout.bounding_poly
    """
    def _walk(x: Any, depth: int) -> list[float] | None:
        if depth > max_depth:
            return None

        if isinstance(x, dict):
            # case 1: 直接有 bounding_poly
            bp = x.get("bounding_poly")
            if isinstance(bp, dict):
                vertices = get_vertices_from_bounding_poly(
                    bounding_poly=bp,
                    image_width=image_width,
                    image_height=image_height,
                )
                bbox = polygon_to_coco_bbox(vertices)
                if bbox is not None:
                    return bbox

            # case 2: 直接有 layout.bounding_poly
            layout = x.get("layout")
            if isinstance(layout, dict):
                bp = layout.get("bounding_poly")
                if isinstance(bp, dict):
                    vertices = get_vertices_from_bounding_poly(
                        bounding_poly=bp,
                        image_width=image_width,
                        image_height=image_height,
                    )
                    bbox = polygon_to_coco_bbox(vertices)
                    if bbox is not None:
                        return bbox

            # case 3: vertices / normalized_vertices 直接掛在這層
            vertices = x.get("vertices")
            if isinstance(vertices, list) and vertices:
                pts = []
                for pt in vertices:
                    if not isinstance(pt, dict):
                        continue
                    px = pt.get("x")
                    py = pt.get("y")
                    if px is None or py is None:
                        continue
                    pts.append((float(px), float(py)))
                bbox = polygon_to_coco_bbox(pts)
                if bbox is not None:
                    return bbox

            normalized_vertices = x.get("normalized_vertices")
            if isinstance(normalized_vertices, list) and normalized_vertices:
                pts = []
                for pt in normalized_vertices:
                    if not isinstance(pt, dict):
                        continue
                    px = pt.get("x")
                    py = pt.get("y")
                    if px is None or py is None:
                        continue
                    pts.append((float(px) * image_width, float(py) * image_height))
                bbox = polygon_to_coco_bbox(pts)
                if bbox is not None:
                    return bbox

            # case 4: bbox array
            bbox = x.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                try:
                    a, b, c, d = [float(v) for v in bbox]
                    # 盡量容忍兩種格式：
                    # [x1, y1, x2, y2] 或 [x, y, w, h]
                    if c > a and d > b:
                        # 優先視為 xyxy
                        return [round(a, 2), round(b, 2), round(c - a, 2), round(d - b, 2)]
                except (TypeError, ValueError):
                    pass

            # 繼續往下找
            for v in x.values():
                found = _walk(v, depth + 1)
                if found is not None:
                    return found

        elif isinstance(x, list):
            for item in x:
                found = _walk(item, depth + 1)
                if found is not None:
                    return found

        return None

    return _walk(node, 0)


def map_layout_block_to_category(block: dict) -> tuple[int | None, str]:
    """
    第一版 mapping：
    - table_block -> Table
    - text_block.type_ == paragraph -> Text
    - text_block.type_ == heading-1 -> Title
    - text_block.type_ in heading-2/3/4 -> Section-header
    - list_block -> Text
    - header/footer -> ignore
    """
    if not isinstance(block, dict):
        return None, "not_dict"

    if "table_block" in block:
        return TABLE_CATEGORY_ID, "Table"

    if "list_block" in block:
        return TEXT_CATEGORY_ID, "Text(list_block)"

    text_block = block.get("text_block")
    if isinstance(text_block, dict):
        t = text_block.get("type_")

        if t == "paragraph":
            return TEXT_CATEGORY_ID, "Text"

        if t == "heading-1":
            return TITLE_CATEGORY_ID, "Title"

        if t in {"heading-2", "heading-3", "heading-4"}:
            return SECTION_HEADER_CATEGORY_ID, "Section-header"

        if t in {"header", "footer"}:
            return None, f"ignore:{t}"

        if isinstance(t, str):
            # 其他未知 text_block 類型，先保守視為 Text
            return TEXT_CATEGORY_ID, f"Text({t})"

        return TEXT_CATEGORY_ID, "Text(text_block)"

    return None, "unknown_block"


def iter_layout_blocks(block: Any):
    """
    遞迴走訪 document_layout.blocks tree。
    """
    if not isinstance(block, dict):
        return

    yield block

    # wrapper 可能是 text_block / table_block / list_block
    for wrapper_key in ("text_block", "table_block", "list_block"):
        wrapper_obj = block.get(wrapper_key)
        if isinstance(wrapper_obj, dict):
            inner_blocks = wrapper_obj.get("blocks")
            if isinstance(inner_blocks, list):
                for child in inner_blocks:
                    yield from iter_layout_blocks(child)

            # table/list 裡面可能更深層巢狀
            yield from iter_blocks_in_nested_container(wrapper_obj)


def iter_blocks_in_nested_container(node: Any):
    """
    在 table_block / list_block 的更深層結構裡找 blocks。
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "blocks" and isinstance(v, list):
                for child in v:
                    yield from iter_layout_blocks(child)
            else:
                yield from iter_blocks_in_nested_container(v)

    elif isinstance(node, list):
        for item in node:
            yield from iter_blocks_in_nested_container(item)


def collect_root_blocks(doc: dict) -> list[dict]:
    if not isinstance(doc, dict):
        return []

    document_layout = doc.get("document_layout")
    if not isinstance(document_layout, dict):
        return []

    blocks = document_layout.get("blocks")
    if not isinstance(blocks, list):
        return []

    return [b for b in blocks if isinstance(b, dict)]


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not RAW_DIR.exists():
        raise SystemExit(f"DocAI LAYOUT raw dir not found: {RAW_DIR}")

    PRED_DIR.mkdir(parents=True, exist_ok=True)

    gt = load_json(GT_FILE)
    gt_images = gt["images"]

    image_id_to_info = {img["id"]: img for img in gt_images}
    stem_to_image_id = {Path(img["file_name"]).stem: img["id"] for img in gt_images}

    preds = []

    mapped_counter = Counter()
    skipped_counter = Counter()
    no_bbox_counter = Counter()
    file_pred_counter = Counter()
    wrapper_counter = Counter()

    json_paths = sorted(RAW_DIR.glob("*.json"))

    for json_path in json_paths:
        stem = json_path.stem

        # 只處理 GT 裡有對應的 sample
        if stem not in stem_to_image_id:
            skipped_counter["not_in_gt"] += 1
            continue

        image_id = stem_to_image_id[stem]
        gt_img_info = image_id_to_info[image_id]
        image_width, image_height = get_page_size_from_gt(gt_img_info)

        doc = load_json(json_path)
        root_blocks = collect_root_blocks(doc)
        if not root_blocks:
            skipped_counter["no_root_blocks"] += 1
            continue

        for root_block in root_blocks:
            for block in iter_layout_blocks(root_block):
                if not isinstance(block, dict):
                    continue

                if "text_block" in block:
                    wrapper_counter["text_block"] += 1
                elif "table_block" in block:
                    wrapper_counter["table_block"] += 1
                elif "list_block" in block:
                    wrapper_counter["list_block"] += 1
                else:
                    wrapper_counter["unknown"] += 1

                category_id, mapped_name = map_layout_block_to_category(block)
                if category_id is None:
                    skipped_counter[mapped_name] += 1
                    continue

                coco_bbox = find_first_bbox_recursively(
                    node=block,
                    image_width=image_width,
                    image_height=image_height,
                )
                if coco_bbox is None:
                    no_bbox_counter[mapped_name] += 1
                    continue

                preds.append({
                    "image_id": image_id,
                    "category_id": category_id,
                    "bbox": coco_bbox,
                    "score": DEFAULT_SCORE,
                })
                mapped_counter[mapped_name] += 1
                file_pred_counter[stem] += 1

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_predictions: {len(preds)}")

    print("\n[INFO] wrapper types seen]")
    for label, count in wrapper_counter.most_common():
        print(f"  {label}: {count}")
    if not wrapper_counter:
        print("  (none)")

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

    print("\n[INFO] skipped items")
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