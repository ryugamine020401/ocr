from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from jiwer import cer, wer
from paddleocr import PaddleOCR


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

MANIFEST = DATA / "manifest.csv"
GT_DIR = DATA / "gt"

PRED_DIR = DATA / "pred" / "paddle"
OUT_CSV = DATA / "results_paddle.csv"


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def normalize_for_eval(s: str) -> str:
    s = s.lower()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    return s.strip()


def clear_dir_files(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0

    removed = 0
    for p in dir_path.iterdir():
        if p.is_file():
            p.unlink()
            removed += 1
    return removed


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")

    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit("manifest is empty")

    required = {"id", "image_path"}
    actual = set(rows[0].keys())
    if not required.issubset(actual):
        raise SystemExit(f"manifest missing columns: {required}")

    return rows


def iter_texts_from_ocr_result(result: Any) -> Iterable[str]:
    """
    兼容 PaddleOCR 不同版本可能回傳的結構。
    """
    if result is None:
        return []

    out: list[str] = []

    # 舊版常見: [ [box, (text, score)], ... ]
    if isinstance(result, list):
        # unwrap one level
        if (
            len(result) == 1
            and isinstance(result[0], list)
            and result[0]
            and all(isinstance(d, (list, tuple)) and len(d) >= 2 for d in result[0])
        ):
            result = result[0]

        for det in result:
            if not isinstance(det, (list, tuple)) or len(det) < 2:
                continue

            payload = det[1]
            if isinstance(payload, (list, tuple)) and len(payload) >= 1:
                text = payload[0]
            else:
                text = payload

            if isinstance(text, str):
                s = text.strip()
                if s:
                    out.append(s)

        if out:
            return out

    # 新版 predict() 有時回傳物件/list[dict]
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                rec_texts = item.get("rec_texts")
                if isinstance(rec_texts, list):
                    for t in rec_texts:
                        if isinstance(t, str) and t.strip():
                            out.append(t.strip())

    return out


def run_paddle_predictions(rows: list[dict]) -> None:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    removed_count = clear_dir_files(PRED_DIR)

    ocr = PaddleOCR(
        use_textline_orientation=True,
        lang="en",
    )

    success_count = 0

    for r in rows:
        _id = r["id"].strip()
        image_path = Path(r["image_path"]).expanduser()

        if not image_path.exists():
            raise SystemExit(f"missing image_path for id={_id}: {image_path}")

        print(f"[PaddleOCR] processing {_id}...")

        result = ocr.predict(str(image_path))
        lines = list(iter_texts_from_ocr_result(result))
        text_out = normalize_text("\n".join(lines))

        out_path = PRED_DIR / f"{_id}.txt"
        out_path.write_text(text_out, encoding="utf-8")
        success_count += 1

    print(f"[OK] cleared {removed_count} old files from -> {PRED_DIR}")
    print(f"[OK] wrote {success_count} prediction files -> {PRED_DIR}")


def evaluate_predictions(rows: list[dict]) -> None:
    if not GT_DIR.exists():
        raise SystemExit(f"gt dir not found: {GT_DIR}")

    if not PRED_DIR.exists():
        raise SystemExit(f"pred dir not found: {PRED_DIR}")

    results: list[dict[str, str]] = []
    cer_list: list[float] = []
    wer_list: list[float] = []

    for r in rows:
        _id = r["id"].strip()
        gt_path = GT_DIR / f"{_id}.txt"
        pred_path = PRED_DIR / f"{_id}.txt"

        if not gt_path.exists():
            raise SystemExit(f"missing gt: {gt_path}")
        if not pred_path.exists():
            raise SystemExit(f"missing pred: {pred_path}")

        gt = normalize_for_eval(gt_path.read_text(encoding="utf-8-sig", errors="ignore"))
        pred = normalize_for_eval(pred_path.read_text(encoding="utf-8-sig", errors="ignore"))

        c = cer(gt, pred)
        w = wer(gt, pred)

        cer_list.append(c)
        wer_list.append(w)

        results.append(
            {
                "id": _id,
                "cer": f"{c:.6f}",
                "wer": f"{w:.6f}",
                "gt_chars": str(len(gt)),
                "pred_chars": str(len(pred)),
            }
        )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "cer", "wer", "gt_chars", "pred_chars"],
        )
        writer.writeheader()
        writer.writerows(results)

    avg_cer = sum(cer_list) / len(cer_list)
    avg_wer = sum(wer_list) / len(wer_list)

    worst = sorted(results, key=lambda x: float(x["cer"]), reverse=True)[:5]

    print(f"[OK] wrote -> {OUT_CSV}")
    print(f"[AVG] CER={avg_cer:.6f}  WER={avg_wer:.6f}")
    print("[WORST 5 by CER]")
    for r in worst:
        print(f"  {r['id']}: CER={r['cer']} WER={r['wer']}")


def main() -> None:
    rows = load_manifest()
    run_paddle_predictions(rows)
    evaluate_predictions(rows)


if __name__ == "__main__":
    main()