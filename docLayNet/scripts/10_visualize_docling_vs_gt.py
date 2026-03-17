from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample20.json"
PRED_FILE = ROOT / "outputs" / "pred" / "pred_docling_sample20.json"
IMAGES_DIR = ROOT / "outputs" / "images"
VIS_DIR = ROOT / "outputs" / "vis_docling"

MAX_IMAGES = 20

CATEGORY_ID_TO_NAME = {
    0: "Picture",
    1: "Section-header",
    2: "Table",
    3: "Text",
    4: "Title",
}

GT_COLOR = (0, 255, 0)      # 綠色
PRED_COLOR = (255, 0, 0)    # 紅色


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def xywh_to_xyxy(bbox: list[float]) -> tuple[float, float, float, float]:
    x, y, w, h = bbox
    return x, y, x + w, y + h


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not PRED_FILE.exists():
        raise SystemExit(f"Prediction file not found: {PRED_FILE}")
    if not IMAGES_DIR.exists():
        raise SystemExit(f"Images dir not found: {IMAGES_DIR}")

    VIS_DIR.mkdir(parents=True, exist_ok=True)

    gt = load_json(GT_FILE)
    preds = load_json(PRED_FILE)

    images = gt["images"]
    annotations = gt["annotations"]

    gt_by_image = {}
    for ann in annotations:
        gt_by_image.setdefault(ann["image_id"], []).append(ann)

    pred_by_image = {}
    for pred in preds:
        pred_by_image.setdefault(pred["image_id"], []).append(pred)

    done = 0

    for img_info in images[:MAX_IMAGES]:
        image_id = img_info["id"]
        file_name = img_info["file_name"]
        image_path = IMAGES_DIR / file_name

        if not image_path.exists():
            print(f"[WARN] image not found, skip: {image_path}")
            continue

        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        # 畫 GT
        for ann in gt_by_image.get(image_id, []):
            x1, y1, x2, y2 = xywh_to_xyxy(ann["bbox"])
            cid = ann["category_id"]
            cname = CATEGORY_ID_TO_NAME.get(cid, str(cid))

            draw.rectangle([x1, y1, x2, y2], outline=GT_COLOR, width=3)
            draw.text((x1 + 2, y1 + 2), f"GT:{cname}", fill=GT_COLOR)

        # 畫 Docling prediction
        for pred in pred_by_image.get(image_id, []):
            x1, y1, x2, y2 = xywh_to_xyxy(pred["bbox"])
            cid = pred["category_id"]
            score = pred.get("score", 0.0)
            cname = CATEGORY_ID_TO_NAME.get(cid, str(cid))

            draw.rectangle([x1, y1, x2, y2], outline=PRED_COLOR, width=2)
            draw.text((x1 + 2, y1 + 18), f"D:{cname} {score:.2f}", fill=PRED_COLOR)

        out_path = VIS_DIR / file_name
        image.save(out_path)

        print(f"[OK] saved: {out_path}")
        done += 1

    print(f"[OK] visualized {done} images to: {VIS_DIR}")


if __name__ == "__main__":
    main()