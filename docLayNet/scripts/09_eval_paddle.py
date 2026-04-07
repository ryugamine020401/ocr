from __future__ import annotations

import json
from pathlib import Path

from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
OUTPUTS = ROOT / "outputs"

GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
PRED_JSON = OUTPUTS / "pred" / "pred_paddle_sample30.json"

EVAL_DIR = OUTPUTS / "eval"
FILTERED_PRED_JSON = EVAL_DIR / "pred_paddle_sample30.filtered.json"
OUT_TXT = EVAL_DIR / "paddle_eval.txt"


def main() -> None:
    if not GT_JSON.exists():
        raise SystemExit(f"Missing GT json: {GT_JSON}")

    if not PRED_JSON.exists():
        raise SystemExit(f"Missing prediction json: {PRED_JSON}")

    preds = json.loads(PRED_JSON.read_text(encoding="utf-8"))
    if not isinstance(preds, list) or not preds:
        raise SystemExit("Prediction json is empty or not a list.")

    print(f"[INFO] GT   : {GT_JSON}")
    print(f"[INFO] PRED : {PRED_JSON}")
    print(f"[INFO] num_predictions (raw) = {len(preds)}")

    coco_gt = COCO(str(GT_JSON))
    gt_img_ids = set(coco_gt.getImgIds())

    raw_img_ids = sorted(
        {
            int(p["image_id"])
            for p in preds
            if isinstance(p, dict) and "image_id" in p
        }
    )

    filtered_preds = []
    dropped_preds = []

    for p in preds:
        if not isinstance(p, dict):
            continue

        image_id = p.get("image_id")
        if image_id in gt_img_ids:
            filtered_preds.append(p)
        else:
            dropped_preds.append(p)

    filtered_img_ids = sorted(
        {
            int(p["image_id"])
            for p in filtered_preds
            if isinstance(p, dict) and "image_id" in p
        }
    )
    dropped_img_ids = sorted(
        {
            int(p["image_id"])
            for p in dropped_preds
            if isinstance(p, dict) and "image_id" in p
        }
    )

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    FILTERED_PRED_JSON.write_text(
        json.dumps(filtered_preds, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[INFO] gt_num_images           = {len(gt_img_ids)}")
    print(f"[INFO] pred_num_images (raw)   = {len(raw_img_ids)}")
    print(f"[INFO] pred_num_images (valid) = {len(filtered_img_ids)}")
    print(f"[INFO] dropped_predictions     = {len(dropped_preds)}")
    print(f"[INFO] dropped_image_ids       = {dropped_img_ids}")
    print(f"[INFO] filtered_pred_json      = {FILTERED_PRED_JSON}")

    if not filtered_preds:
        raise SystemExit("No valid predictions remain after filtering by GT image ids.")

    coco_dt = coco_gt.loadRes(str(FILTERED_PRED_JSON))

    coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
    coco_eval.params.imgIds = filtered_img_ids

    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    stats = coco_eval.stats

    summary = (
        "=== Paddle COCO Eval ===\n"
        f"GT_JSON         = {GT_JSON}\n"
        f"PRED_JSON       = {PRED_JSON}\n"
        f"FILTERED_PRED   = {FILTERED_PRED_JSON}\n"
        f"num_pred_raw    = {len(preds)}\n"
        f"num_pred_valid  = {len(filtered_preds)}\n"
        f"dropped_pred    = {len(dropped_preds)}\n"
        f"dropped_img_ids = {dropped_img_ids}\n"
        f"eval_img_count  = {len(filtered_img_ids)}\n"
        "\n"
        f"AP@[0.50:0.95] = {stats[0]:.6f}\n"
        f"AP@0.50        = {stats[1]:.6f}\n"
        f"AP@0.75        = {stats[2]:.6f}\n"
        f"AP_small       = {stats[3]:.6f}\n"
        f"AP_medium      = {stats[4]:.6f}\n"
        f"AP_large       = {stats[5]:.6f}\n"
        f"AR@1           = {stats[6]:.6f}\n"
        f"AR@10          = {stats[7]:.6f}\n"
        f"AR@100         = {stats[8]:.6f}\n"
        f"AR_small       = {stats[9]:.6f}\n"
        f"AR_medium      = {stats[10]:.6f}\n"
        f"AR_large       = {stats[11]:.6f}\n"
    )

    OUT_TXT.write_text(summary, encoding="utf-8")

    print("\n=== SAVED SUMMARY ===")
    print(summary)
    print(f"[OK] saved: {OUT_TXT}")


if __name__ == "__main__":
    main()