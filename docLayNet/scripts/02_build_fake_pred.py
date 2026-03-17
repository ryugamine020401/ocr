from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

INPUT_GT = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
OUTPUT_PRED_DIR = ROOT / "outputs" / "pred"
OUT_FILE = OUTPUT_PRED_DIR / "pred_fake_sample30.json"

# bbox 位移比例，讓 fake prediction 跟 GT 很像，但不是完全一樣
SHIFT_X = 3.0
SHIFT_Y = 3.0
SCALE_W = 0.98
SCALE_H = 0.98

# fake confidence score
DEFAULT_SCORE = 0.95


def clamp_bbox(x: float, y: float, w: float, h: float, img_w: float, img_h: float) -> list[float]:
    x = max(0.0, x)
    y = max(0.0, y)
    w = max(1.0, w)
    h = max(1.0, h)

    if x + w > img_w:
        w = max(1.0, img_w - x)
    if y + h > img_h:
        h = max(1.0, img_h - y)

    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def main() -> None:
    OUTPUT_PRED_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_GT.exists():
        raise SystemExit(f"GT not found: {INPUT_GT}")

    with INPUT_GT.open("r", encoding="utf-8") as f:
        coco_gt = json.load(f)

    image_map = {img["id"]: img for img in coco_gt["images"]}

    preds = []

    for ann in coco_gt["annotations"]:
        image_id = ann["image_id"]
        img_info = image_map[image_id]
        img_w = float(img_info["width"])
        img_h = float(img_info["height"])

        x, y, w, h = ann["bbox"]

        # 做一點小偏移和縮放
        new_x = float(x) + SHIFT_X
        new_y = float(y) + SHIFT_Y
        new_w = float(w) * SCALE_W
        new_h = float(h) * SCALE_H

        pred_bbox = clamp_bbox(new_x, new_y, new_w, new_h, img_w, img_h)

        preds.append({
            "image_id": image_id,
            "category_id": ann["category_id"],
            "bbox": pred_bbox,   # COCO prediction bbox: [x, y, w, h]
            "score": DEFAULT_SCORE,
        })

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_predictions: {len(preds)}")


if __name__ == "__main__":
    main()