from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "docling_raw"
IMAGES_DIR = ROOT / "outputs" / "images"
OUT_DIR = ROOT / "outputs" / "debug" / "docling"

START_ID = 1
END_ID = 30

CATEGORY_COLOR = {
    "picture": (255, 0, 0),          # red
    "table": (0, 0, 255),            # blue
    "section_header": (255, 128, 0), # orange
    "section-header": (255, 128, 0),
    "text": (0, 180, 0),             # green
    "title": (180, 0, 180),          # purple
    "document_title": (180, 0, 180),
    "page_header": (120, 120, 0),
    "page_footer": (120, 120, 0),
    "list_item": (0, 180, 180),
    "list": (0, 180, 180),
    "caption": (100, 100, 100),
    "key_value_area": (180, 80, 80),
}

DEFAULT_COLOR = (255, 0, 255)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_page_height(doc: dict, fallback_height: float) -> float:
    pages = doc.get("pages", {})
    page1 = pages.get("1") or pages.get(1) or {}
    size = page1.get("size", {})
    h = size.get("height")
    try:
        return float(h)
    except (TypeError, ValueError):
        return float(fallback_height)


def collect_page_bboxes(item: dict, page_no: int = 1) -> list[dict]:
    out = []
    prov_list = item.get("prov", [])
    if not isinstance(prov_list, list):
        return out

    for prov in prov_list:
        if not isinstance(prov, dict):
            continue
        if prov.get("page_no") != page_no:
            continue

        bbox = prov.get("bbox")
        if not isinstance(bbox, dict):
            continue
        if bbox.get("coord_origin") != "BOTTOMLEFT":
            continue
        if not all(k in bbox for k in ("l", "r", "t", "b")):
            continue

        out.append(bbox)

    return out


def union_bottomleft_bboxes(bboxes: list[dict]) -> dict:
    return {
        "l": min(float(b["l"]) for b in bboxes),
        "r": max(float(b["r"]) for b in bboxes),
        "t": max(float(b["t"]) for b in bboxes),
        "b": min(float(b["b"]) for b in bboxes),
        "coord_origin": "BOTTOMLEFT",
    }


def bottomleft_to_xyxy(
    bbox: dict, image_height: float
) -> tuple[float, float, float, float]:
    l = float(bbox["l"])
    r = float(bbox["r"])
    t = float(bbox["t"])
    b = float(bbox["b"])

    x1 = l
    y1 = image_height - t
    x2 = r
    y2 = image_height - b
    return x1, y1, x2, y2


def extract_items(doc: dict) -> list[dict]:
    items = []

    for section in ["pictures", "tables", "texts", "key_value_items", "form_items"]:
        for item in doc.get(section, []):
            if isinstance(item, dict):
                items.append(item)

    return items


def process_one(sample_id: str) -> bool:
    raw_json = RAW_DIR / sample_id / f"{sample_id}.json"
    image_path = IMAGES_DIR / f"{sample_id}.png"
    out_path = OUT_DIR / f"{sample_id}.png"

    if not raw_json.exists():
        print(f"[WARN] Docling json not found, skip: {raw_json}")
        return False

    if not image_path.exists():
        print(f"[WARN] image not found, skip: {image_path}")
        return False

    doc = load_json(raw_json)
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    img_w, img_h = image.size
    page_height = get_page_height(doc, img_h)

    print(f"[INFO] sample={sample_id} image size : {img_w} x {img_h}")
    print(f"[INFO] sample={sample_id} page height: {page_height}")

    items = extract_items(doc)
    drawn = 0

    for item in items:
        label = str(item.get("label", "unknown"))
        bboxes = collect_page_bboxes(item, page_no=1)
        if not bboxes:
            continue

        merged_bbox = union_bottomleft_bboxes(bboxes)
        x1, y1, x2, y2 = bottomleft_to_xyxy(merged_bbox, page_height)

        color = CATEGORY_COLOR.get(label, DEFAULT_COLOR)

        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        draw.text((x1 + 2, y1 + 2), label, fill=color)

        drawn += 1

    image.save(out_path)

    print(f"[OK] saved: {out_path}")
    print(f"[OK] sample={sample_id} num_boxes_drawn: {drawn}")
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    done = 0
    for i in range(START_ID, END_ID + 1):
        sample_id = str(i)
        ok = process_one(sample_id)
        if ok:
            done += 1

    print(f"[OK] finished. generated {done} images to: {OUT_DIR}")


if __name__ == "__main__":
    main()