from __future__ import annotations

import json
from pathlib import Path

from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
OUTPUTS = ROOT / "outputs"

GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
PRED_JSON = OUTPUTS / "pred" / "pred_mineru_sample30.json"

EVAL_DIR = OUTPUTS / "eval"
OUT_TXT = EVAL_DIR / "mineru_eval.txt"


def main() -> None:
    if not GT_JSON.exists():
        raise SystemExit(f"Missing GT json: {GT_JSON}")

    if not PRED_JSON.exists():
        raise SystemExit(f"Missing prediction json: {PRED_JSON}")

    preds = json.loads(PRED_JSON.read_text(encoding="utf-8"))
    if not preds:
        raise SystemExit("Prediction json is empty.")

    print(f"[INFO] GT   : {GT_JSON}")
    print(f"[INFO] PRED : {PRED_JSON}")
    print(f"[INFO] num_predictions = {len(preds)}")

    coco_gt = COCO(str(GT_JSON))
    coco_dt = coco_gt.loadRes(str(PRED_JSON))

    coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    stats = coco_eval.stats

    summary = (
        "=== MinerU COCO Eval ===\n"
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

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(summary, encoding="utf-8")

    print("\n=== SAVED SUMMARY ===")
    print(summary)
    print(f"[OK] saved: {OUT_TXT}")


if __name__ == "__main__":
    main()