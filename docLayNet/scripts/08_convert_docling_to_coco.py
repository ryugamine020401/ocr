from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
RAW_DIR = ROOT / "outputs" / "docling_raw"
PRED_DIR = ROOT / "outputs" / "pred"
OUT_FILE = PRED_DIR / "pred_docling_sample30.json"

# 與你的 GT 嚴格對齊：
# 7 -> 0 Picture
# 8 -> 1 Section-header
# 9 -> 2 Table
# 10 -> 3 Text
# 11 -> 4 Title
#
# 目前 Docling 統計中沒有穩定出現 title / document_title，
# 因此這裡先不要硬映射 Title，避免誤報。
LABEL_TO_CATEGORY_ID = {
    "picture": 0,
    "section_header": 1,
    "section-header": 1,
    "table": 2,
    "text": 3,
}

DEFAULT_SCORE = 0.99


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def bbox_bottomleft_to_coco(bbox: dict, image_height: float) -> list[float]:
    """
    Docling bbox:
      l, t, r, b with coord_origin = BOTTOMLEFT

    COCO bbox:
      [x, y, w, h] with origin = TOPLEFT
    """
    l = float(bbox["l"])
    r = float(bbox["r"])
    t = float(bbox["t"])
    b = float(bbox["b"])

    x = l
    y = image_height - t
    w = max(r - l, 1.0)
    h = max(t - b, 1.0)

    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def is_child_of_picture(item: dict) -> bool:
    parent = item.get("parent", {})
    ref = parent.get("$ref", "")
    return isinstance(ref, str) and ref.startswith("#/pictures/")


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


def extract_prediction_items(doc: dict) -> list[dict]:
    """
    只抽目前評測可能用到的主要區塊來源。
    不把 picture 內部的 text 重複算進來。
    """
    items = []

    for item in doc.get("pictures", []):
        if isinstance(item, dict):
            items.append(item)

    for item in doc.get("tables", []):
        if isinstance(item, dict):
            items.append(item)

    for item in doc.get("texts", []):
        if not isinstance(item, dict):
            continue
        if is_child_of_picture(item):
            continue
        items.append(item)

    return items


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not RAW_DIR.exists():
        raise SystemExit(f"Docling raw dir not found: {RAW_DIR}")

    PRED_DIR.mkdir(parents=True, exist_ok=True)

    gt = load_json(GT_FILE)
    gt_images = gt["images"]

    image_id_to_info = {img["id"]: img for img in gt_images}
    stem_to_image_id = {Path(img["file_name"]).stem: img["id"] for img in gt_images}

    preds = []
    raw_subdirs = sorted(p for p in RAW_DIR.iterdir() if p.is_dir())

    mapped_label_counter = Counter()
    unmapped_label_counter = Counter()
    no_bbox_label_counter = Counter()
    file_pred_counter = Counter()

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
        gt_img_info = image_id_to_info[image_id]

        doc = load_json(json_path)
        page_height = get_page_height(doc, float(gt_img_info["height"]))
        items = extract_prediction_items(doc)

        for item in items:
            label = str(item.get("label", ""))
            category_id = LABEL_TO_CATEGORY_ID.get(label)

            if category_id is None:
                unmapped_label_counter[label] += 1
                continue

            bboxes = collect_page_bboxes(item, page_no=1)
            if not bboxes:
                no_bbox_label_counter[label] += 1
                continue

            merged_bbox = union_bottomleft_bboxes(bboxes)
            coco_bbox = bbox_bottomleft_to_coco(merged_bbox, page_height)

            preds.append({
                "image_id": image_id,
                "category_id": category_id,
                "bbox": coco_bbox,
                "score": DEFAULT_SCORE,
            })

            mapped_label_counter[label] += 1
            file_pred_counter[stem] += 1

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_predictions: {len(preds)}")

    print("\n[INFO] mapped labels")
    if mapped_label_counter:
        for label, count in mapped_label_counter.most_common():
            print(f"  {label}: {count}")
    else:
        print("  (none)")

    print("\n[INFO] unmapped labels")
    if unmapped_label_counter:
        for label, count in unmapped_label_counter.most_common():
            print(f"  {label}: {count}")
    else:
        print("  (none)")

    print("\n[INFO] mapped labels but no usable bbox")
    if no_bbox_label_counter:
        for label, count in no_bbox_label_counter.most_common():
            print(f"  {label}: {count}")
    else:
        print("  (none)")

    print("\n[INFO] predictions per file")
    def sort_key(item):
        stem = item[0]
        if stem.isdigit():
            return (0, int(stem))
        return (1, stem)

    for stem, count in sorted(file_pred_counter.items(), key=sort_key):
        print(f"  {stem}: {count}")


if __name__ == "__main__":
    main()