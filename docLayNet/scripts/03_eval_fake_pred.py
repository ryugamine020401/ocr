from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

GT_FILE = ROOT / "outputs" / "gt" / "gt_5class_sample30.json"
PRED_FILE = ROOT / "outputs" / "pred" / "pred_fake_sample30.json"
OUTPUT_EVAL_DIR = ROOT / "outputs" / "eval"
SUMMARY_TXT = OUTPUT_EVAL_DIR / "eval_fake_sample30.txt"
SUMMARY_JSON = OUTPUT_EVAL_DIR / "eval_fake_sample30.json"


def main() -> None:
    OUTPUT_EVAL_DIR.mkdir(parents=True, exist_ok=True)

    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")
    if not PRED_FILE.exists():
        raise SystemExit(f"Prediction file not found: {PRED_FILE}")

    print(f"[INFO] GT   : {GT_FILE}")
    print(f"[INFO] Pred : {PRED_FILE}")

    coco_gt = COCO(str(GT_FILE))
    coco_dt = coco_gt.loadRes(str(PRED_FILE))

    coco_eval = COCOeval(coco_gt, coco_dt, iouType="bbox")

    log_buffer = io.StringIO()
    with contextlib.redirect_stdout(log_buffer):
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()

    summary_text = log_buffer.getvalue()

    stats = {
        "AP@[0.50:0.95]": float(coco_eval.stats[0]),
        "AP@0.50": float(coco_eval.stats[1]),
        "AP@0.75": float(coco_eval.stats[2]),
        "AP_small": float(coco_eval.stats[3]),
        "AP_medium": float(coco_eval.stats[4]),
        "AP_large": float(coco_eval.stats[5]),
        "AR@1": float(coco_eval.stats[6]),
        "AR@10": float(coco_eval.stats[7]),
        "AR@100": float(coco_eval.stats[8]),
        "AR_small": float(coco_eval.stats[9]),
        "AR_medium": float(coco_eval.stats[10]),
        "AR_large": float(coco_eval.stats[11]),
    }

    with SUMMARY_TXT.open("w", encoding="utf-8") as f:
        f.write(summary_text)

    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(summary_text)
    print(f"[OK] saved text summary : {SUMMARY_TXT}")
    print(f"[OK] saved json summary : {SUMMARY_JSON}")


if __name__ == "__main__":
    main()