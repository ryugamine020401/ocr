from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
OUTPUTS = ROOT / "outputs"

IMAGES_DIR = OUTPUTS / "images"
GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
PRED_JSON = OUTPUTS / "pred" / "pred_mineru_sample30.json"
OUT_DIR = OUTPUTS / "vis_mineru"

CATEGORY_ID_TO_NAME = {
    0: "Picture",
    1: "Section-header",
    2: "Table",
    3: "Text",
    4: "Title",
}


def xywh_to_xyxy(bbox: list[float]) -> tuple[float, float, float, float]:
    x, y, w, h = bbox
    return x, y, x + w, y + h


def find_image_path(file_name: str) -> Path:
    p = IMAGES_DIR / Path(file_name).name
    if p.exists():
        return p

    p = OUTPUTS / file_name
    if p.exists():
        return p

    raise FileNotFoundError(f"Image not found for file_name={file_name}")


def main() -> None:
    if not GT_JSON.exists():
        raise SystemExit(f"Missing GT json: {GT_JSON}")
    if not PRED_JSON.exists():
        raise SystemExit(f"Missing prediction json: {PRED_JSON}")

    gt = json.loads(GT_JSON.read_text(encoding="utf-8"))
    pred = json.loads(PRED_JSON.read_text(encoding="utf-8"))

    images = gt["images"]
    annotations = gt["annotations"]

    gt_by_image: dict[int, list[dict]] = {}
    for ann in annotations:
        gt_by_image.setdefault(ann["image_id"], []).append(ann)

    pred_by_image: dict[int, list[dict]] = {}
    for ann in pred:
        pred_by_image.setdefault(ann["image_id"], []).append(ann)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] GT images       : {len(images)}")
    print(f"[INFO] GT annotations  : {len(annotations)}")
    print(f"[INFO] Pred annotations: {len(pred)}")
    print(f"[INFO] Output dir      : {OUT_DIR}")

    saved = 0
    skipped = 0

    for im in images:
        image_id = im["id"]
        file_name = im["file_name"]

        try:
            img_path = find_image_path(file_name)
        except FileNotFoundError as e:
            print(f"[WARN] {e}")
            skipped += 1
            continue

        image = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        # 綠：GT
        for ann in gt_by_image.get(image_id, []):
            x1, y1, x2, y2 = xywh_to_xyxy(ann["bbox"])
            category_name = CATEGORY_ID_TO_NAME.get(ann["category_id"], str(ann["category_id"]))

            draw.rectangle([x1, y1, x2, y2], outline="green", width=2)
            draw.text((x1, max(0, y1 - 12)), category_name, fill="green")

        # 紅：MinerU
        for ann in pred_by_image.get(image_id, []):
            x1, y1, x2, y2 = xywh_to_xyxy(ann["bbox"])
            category_name = CATEGORY_ID_TO_NAME.get(ann["category_id"], str(ann["category_id"]))

            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            draw.text((x1, y1 + 2), category_name, fill="red")

        out_path = OUT_DIR / Path(file_name).name
        image.save(out_path)
        print(f"[OK] saved: {out_path}")
        saved += 1

    print("\n=== DONE ===")
    print(f"[INFO] saved   : {saved}")
    print(f"[INFO] skipped : {skipped}")


if __name__ == "__main__":
    main()