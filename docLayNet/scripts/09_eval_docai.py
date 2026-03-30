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
PRED_DIR = ROOT / "outputs" / "pred"
EVAL_DIR = ROOT / "outputs" / "eval"

PRED_FILES = {
    "docai_ocr": PRED_DIR / "pred_docai_ocr_sample30.json",
    "docai_form": PRED_DIR / "pred_docai_form_sample30.json",
}


def evaluate_one(gt_file: Path, pred_file: Path) -> tuple[str, dict]:
    if not pred_file.exists():
        raise FileNotFoundError(f"Prediction file not found: {pred_file}")

    with pred_file.open("r", encoding="utf-8") as f:
        preds = json.load(f)

    print(f"[INFO] Pred : {pred_file}")
    print(f"[INFO] num_predictions: {len(preds)}")

    coco_gt = COCO(str(gt_file))
    coco_dt = coco_gt.loadRes(preds)

    coco_eval = COCOeval(coco_gt, coco_dt, iouType="bbox")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()

    summary_text = buf.getvalue()

    stats = {
        "num_predictions": int(len(preds)),
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

    return summary_text, stats


def main() -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    if not GT_FILE.exists():
        raise SystemExit(f"GT file not found: {GT_FILE}")

    print(f"[INFO] GT : {GT_FILE}")

    all_results = {}

    for name, pred_file in PRED_FILES.items():
        print("=" * 80)
        print(f"[INFO] evaluating: {name}")

        summary_text, stats = evaluate_one(GT_FILE, pred_file)

        summary_txt_path = EVAL_DIR / f"eval_{name}_sample30.txt"
        summary_json_path = EVAL_DIR / f"eval_{name}_sample30.json"

        with summary_txt_path.open("w", encoding="utf-8") as f:
            f.write(summary_text)

        with summary_json_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(summary_text)
        print(f"[OK] saved text summary : {summary_txt_path}")
        print(f"[OK] saved json summary : {summary_json_path}")

        all_results[name] = stats

    compare_json_path = EVAL_DIR / "eval_docai_compare_sample30.json"
    with compare_json_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print("[COMPARE]")
    for name, stats in all_results.items():
        print(
            f"  {name}: "
            f"AP@[0.50:0.95]={stats['AP@[0.50:0.95]']:.3f}, "
            f"AP@0.50={stats['AP@0.50']:.3f}, "
            f"AP@0.75={stats['AP@0.75']:.3f}, "
            f"AR@100={stats['AR@100']:.3f}, "
            f"num_predictions={stats['num_predictions']}"
        )

    print(f"[OK] saved compare json : {compare_json_path}")


if __name__ == "__main__":
    main()