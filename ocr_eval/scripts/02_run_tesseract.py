from __future__ import annotations

import csv
import json
from pathlib import Path

from jiwer import cer, wer


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

MANIFEST = DATA / "manifest.csv"

GT_DIR = DATA / "gt"
GT_SUMMARY = DATA / "gt_summary.csv"

PRED_DIR = DATA / "pred" / "tesseract"
OUT_CSV = DATA / "results_tesseract.csv"


def extract_text_msocr(obj: dict) -> str:
    """
    從 Microsoft OCR JSON 中抽出純文字。
    優先取 line["text"]，若沒有則回退到 words。
    """
    lines_out: list[str] = []

    for rr in obj.get("recognitionResults", []) or []:
        for line in rr.get("lines", []) or []:
            t = line.get("text")

            if isinstance(t, str) and t.strip():
                lines_out.append(t.strip())
                continue

            words = line.get("words", []) or []
            toks: list[str] = []

            for w in words:
                wt = w.get("text")
                if isinstance(wt, str) and wt.strip():
                    toks.append(wt.strip())

            if toks:
                lines_out.append(" ".join(toks))

    return "\n".join(lines_out).strip()


def clear_dir_files(dir_path: Path) -> int:
    """
    清掉目錄內所有檔案（不遞迴刪資料夾）。
    """
    if not dir_path.exists():
        return 0

    removed = 0
    for p in dir_path.iterdir():
        if p.is_file():
            p.unlink()
            removed += 1
    return removed


def normalize_for_eval(s: str) -> str:
    """
    評估用最小 normalization：
    - 小寫
    - CRLF / CR -> LF
    - 換行視為空白
    - 連續空白壓成單一空白
    - 去頭尾空白
    """
    s = s.lower()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    return s.strip()


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")

    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit("manifest is empty")

    return rows


def build_ground_truth(rows: list[dict]) -> None:
    """
    根據 manifest.csv 裡的 ocr_json_path 建立 GT txt。
    同時輸出 gt_summary.csv
    """
    required = {"id", "ocr_json_path"}
    actual = set(rows[0].keys()) if rows else set()

    if not required.issubset(actual):
        raise SystemExit(f"manifest missing columns: {required}")

    GT_DIR.mkdir(parents=True, exist_ok=True)
    removed_count = clear_dir_files(GT_DIR)

    summary_rows: list[dict[str, str]] = []

    for r in rows:
        _id = r["id"].strip()
        json_path = Path(r["ocr_json_path"]).expanduser()

        if not json_path.exists():
            raise SystemExit(f"missing ocr_json_path for id={_id}: {json_path}")

        with json_path.open("r", encoding="utf-8-sig") as jf:
            obj = json.load(jf)

        text = extract_text_msocr(obj)

        out_txt = GT_DIR / f"{_id}.txt"
        out_txt.write_text(text, encoding="utf-8")

        summary_rows.append(
            {
                "id": _id,
                "gt_txt": str(out_txt),
                "chars": str(len(text)),
                "lines": str(text.count("\n") + (1 if text else 0)),
            }
        )

    with GT_SUMMARY.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "gt_txt", "chars", "lines"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"[OK] cleared {removed_count} old files from -> {GT_DIR}")
    print(f"[OK] wrote {len(summary_rows)} gt txt files -> {GT_DIR}")
    print(f"[OK] summary -> {GT_SUMMARY}")


def evaluate_predictions(rows: list[dict]) -> None:
    """
    讀 GT 與 Tesseract 預測結果，計算 CER / WER。
    """
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
    build_ground_truth(rows)
    evaluate_predictions(rows)


if __name__ == "__main__":
    main()