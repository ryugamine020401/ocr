from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
RAW_DIR = ROOT / "outputs" / "docling_raw"
PRED_DIR = ROOT / "outputs" / "pred"
OUT_FILE = PRED_DIR / "pred_docling_sample30.json"

# Docling label -> 研究用 5 類別 id
LABEL_TO_CATEGORY_ID = {
    "picture": 0,          # Picture
    "section_header": 1,   # Section-header
    "section-header": 1,
    "header": 1,
    "table": 2,            # Table
    "text": 3,             # Text
    "title": 4,            # Title
    "document_title": 4,
}

DEFAULT_SCORE = 0.99


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def bbox_bottomleft_to_coco(bbox: dict, image_height: float) -> list[float]:
    """
    Docling bbox:
      {
        "l": ...,
        "r": ...,
        "t": ...,
        "b": ...,
        "coord_origin": "BOTTOMLEFT"
      }

    Convert to COCO:
      [x, y, w, h]
    where origin is TOPLEFT.
    """
    l = float(bbox["l"])
    r = float(bbox["r"])
    t = float(bbox["t"])
    b = float(bbox["b"])

    x = l
    y = image_height - t
    w = r - l
    h = t - b

    if w < 1:
        w = 1.0
    if h < 1:
        h = 1.0

    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def extract_items(doc: dict) -> list[dict]:
    """
    目前先從這三類抽：
    - texts
    - pictures
    - tables

    後面如果 Docling JSON 有更多欄位，再擴充。
    """
    items = []

    for key in ["texts", "pictures", "tables"]:
        values = doc.get(key, [])
        if isinstance(values, list):
            items.extend(values)

    return items


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not RAW_DIR.exists():
        raise SystemExit(f"Docling raw dir not found: {RAW_DIR}")

    PRED_DIR.mkdir(parents=True, exist_ok=True)

    gt = load_json(GT_FILE)

    # 建 image_id -> image info 映射
    gt_images = gt["images"]
    image_id_to_info = {img["id"]: img for img in gt_images}

    # 建 file stem -> image_id 映射
    # 例如 1.png -> stem = "1"
    stem_to_image_id = {}
    for img in gt_images:
        stem = Path(img["file_name"]).stem
        stem_to_image_id[stem] = img["id"]

    preds = []

    raw_subdirs = sorted([p for p in RAW_DIR.iterdir() if p.is_dir()])

    for subdir in raw_subdirs:
        stem = subdir.name
        json_path = subdir / f"{stem}.json"

        if not json_path.exists():
            print(f"[WARN] skip missing json: {json_path}")
            continue

        if stem not in stem_to_image_id:
            print(f"[WARN] stem not found in GT images: {stem}")
            continue

        image_id = stem_to_image_id[stem]
        img_info = image_id_to_info[image_id]
        image_height = float(img_info["height"])

        doc = load_json(json_path)
        items = extract_items(doc)

        for item in items:
            label = item.get("label", "")
            if label not in LABEL_TO_CATEGORY_ID:
                continue

            prov_list = item.get("prov", [])
            if not prov_list:
                continue

            prov0 = prov_list[0]
            bbox = prov0.get("bbox")
            if not bbox:
                continue

            coord_origin = bbox.get("coord_origin")
            if coord_origin != "BOTTOMLEFT":
                print(f"[WARN] unexpected coord_origin={coord_origin} in {json_path}")

            coco_bbox = bbox_bottomleft_to_coco(bbox, image_height)

            preds.append({
                "image_id": image_id,
                "category_id": LABEL_TO_CATEGORY_ID[label],
                "bbox": coco_bbox,
                "score": DEFAULT_SCORE,
            })

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_predictions: {len(preds)}")


if __name__ == "__main__":
    main()