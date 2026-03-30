from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
IMAGES_DIR = ROOT / "outputs" / "images"

PRED_FILES = {
    "docai_ocr": ROOT / "outputs" / "pred" / "pred_docai_ocr_sample30.json",
    "docai_form": ROOT / "outputs" / "pred" / "pred_docai_form_sample30.json",
}

VIS_DIRS = {
    "docai_ocr": ROOT / "outputs" / "vis_docai_ocr",
    "docai_form": ROOT / "outputs" / "vis_docai_form",
}

MAX_IMAGES = 30

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


def build_group_by_image(items: list[dict], image_id_key: str = "image_id") -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for item in items:
        image_id = item.get(image_id_key)
        if image_id is None:
            continue
        grouped.setdefault(image_id, []).append(item)
    return grouped


def visualize_one_prediction_set(
    pred_name: str,
    gt: dict,
    preds: list[dict],
    vis_dir: Path,
) -> None:
    images = gt["images"]
    annotations = gt["annotations"]

    gt_by_image = build_group_by_image(annotations, image_id_key="image_id")
    pred_by_image = build_group_by_image(preds, image_id_key="image_id")

    vis_dir.mkdir(parents=True, exist_ok=True)

    done = 0

    print("=" * 80)
    print(f"[INFO] visualizing: {pred_name}")
    print(f"[INFO] output dir : {vis_dir}")
    print(f"[INFO] num_predictions: {len(preds)}")

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
            bbox = ann.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = xywh_to_xyxy(bbox)
            cid = ann.get("category_id")
            cname = CATEGORY_ID_TO_NAME.get(cid, str(cid))

            draw.rectangle([x1, y1, x2, y2], outline=GT_COLOR, width=3)
            draw.text((x1 + 2, y1 + 2), f"GT:{cname}", fill=GT_COLOR)

        # 畫 prediction
        for pred in pred_by_image.get(image_id, []):
            bbox = pred.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = xywh_to_xyxy(bbox)
            cid = pred.get("category_id")
            score = pred.get("score", 0.0)
            cname = CATEGORY_ID_TO_NAME.get(cid, str(cid))

            draw.rectangle([x1, y1, x2, y2], outline=PRED_COLOR, width=2)
            draw.text((x1 + 2, y1 + 18), f"P:{cname} {score:.2f}", fill=PRED_COLOR)

        out_path = vis_dir / file_name
        image.save(out_path)

        print(f"[OK] saved: {out_path}")
        done += 1

    print(f"[OK] visualized {done} images to: {vis_dir}")


def main() -> None:
    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not IMAGES_DIR.exists():
        raise SystemExit(f"Images dir not found: {IMAGES_DIR}")

    for name, pred_file in PRED_FILES.items():
        if not pred_file.exists():
            raise SystemExit(f"Prediction file not found: {pred_file}")

    gt = load_json(GT_FILE)

    for name, pred_file in PRED_FILES.items():
        preds = load_json(pred_file)
        visualize_one_prediction_set(
            pred_name=name,
            gt=gt,
            preds=preds,
            vis_dir=VIS_DIRS[name],
        )


if __name__ == "__main__":
    main()