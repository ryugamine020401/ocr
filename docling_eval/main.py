from __future__ import annotations

import csv
import re
from pathlib import Path

from jiwer import cer, wer
from docling.document_converter import DocumentConverter


HERE = Path(__file__).resolve().parent
OCR_EVAL_ROOT = (HERE.parent / "ocr_eval").resolve()

DATA = OCR_EVAL_ROOT / "data"
MANIFEST = DATA / "manifest.csv"

GT_DIR = DATA / "gt"
PRED_DIR = DATA / "pred" / "docling"
OUT_CSV = DATA / "results_docling.csv"

# Docling 原始 markdown 暫存區
DOCLING_OUT_ROOT = HERE / "out_docling_raw"


def md_to_text(md: str) -> str:
    """
    保守型清洗：把 Markdown/HTML table/link/image/code fence 等盡量去掉，
    保留可讀文字，避免把格式符號算進 CER/WER。
    """
    s = md

    # 去掉 code fence
    s = re.sub(r"```.*?```", " ", s, flags=re.DOTALL)

    # 去掉圖片：![alt](url)
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", s)

    # 把連結 [text](url) -> text
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)

    # 去掉 HTML tags
    s = re.sub(r"<[^>]+>", " ", s)

    # 去掉多餘的 markdown 符號（標題/引用/列表）
    s = re.sub(r"^[>#\-\*\+\s]+", "", s, flags=re.MULTILINE)

    # 壓縮空白
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


def normalize_for_eval(s: str) -> str:
    s = s.lower()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    return s.strip()


def run_docling(input_path: Path, converter: DocumentConverter) -> str:
    """
    對單一檔案執行 Docling 轉換，回傳 markdown 字串。
    """
    result = converter.convert(str(input_path))
    doc = result.document
    md = doc.export_to_markdown()
    return md


def generate_predictions(rows: list[dict[str, str]]) -> tuple[int, int]:
    """
    先跑 Docling 預測，輸出到 pred/docling/{id}.txt
    """
    converter = DocumentConverter()

    ok = 0
    failed = 0

    for r in rows:
        _id = (r.get("id") or "").strip()
        if not _id:
            print("[WARN] missing id, skip")
            continue

        image_path = Path((r.get("image_path") or "").strip())
        if not image_path.is_absolute():
            image_path = (OCR_EVAL_ROOT / image_path).resolve()

        if not image_path.exists():
            print(f"[FAIL] {_id}: missing image: {image_path}")
            failed += 1
            continue

        out_txt = PRED_DIR / f"{_id}.txt"
        err_txt = PRED_DIR / f"{_id}.error.txt"

        if out_txt.exists():
            print(f"[SKIP] {_id} exists")
            ok += 1
            continue

        per_file_out = DOCLING_OUT_ROOT / _id
        per_file_out.mkdir(parents=True, exist_ok=True)

        try:
            print(f"[Docling] {_id} ...")

            md = run_docling(image_path, converter)

            # 保存原始 markdown 方便除錯
            md_path = per_file_out / f"{_id}.md"
            md_path.write_text(md, encoding="utf-8")

            text = md_to_text(md)
            out_txt.write_text(text, encoding="utf-8")

            # 若之前有 error log，成功後可刪除
            if err_txt.exists():
                err_txt.unlink()

            ok += 1

        except Exception as e:
            failed += 1
            err_txt.write_text(str(e), encoding="utf-8")
            print(f"[FAIL] {_id}: {e}")

    return ok, failed


def evaluate_predictions(rows: list[dict[str, str]]) -> None:
    """
    讀 gt/{id}.txt 與 pred/docling/{id}.txt 做 CER/WER 評估
    """
    results = []
    cer_list = []
    wer_list = []

    skipped = 0

    for r in rows:
        _id = (r.get("id") or "").strip()
        if not _id:
            continue

        gt_path = GT_DIR / f"{_id}.txt"
        pred_path = PRED_DIR / f"{_id}.txt"

        if not gt_path.exists():
            print(f"[SKIP-EVAL] {_id}: missing gt -> {gt_path}")
            skipped += 1
            continue

        if not pred_path.exists():
            print(f"[SKIP-EVAL] {_id}: missing pred -> {pred_path}")
            skipped += 1
            continue

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

    if not results:
        raise SystemExit("no evaluable results found")

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
    print(f"[EVAL COUNT] {len(results)}  skipped={skipped}")
    print(f"[AVG] CER={avg_cer:.6f}  WER={avg_wer:.6f}")
    print("[WORST 5 by CER]")
    for r in worst:
        print(f"  {r['id']}: CER={r['cer']} WER={r['wer']}")


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")
    if not GT_DIR.exists():
        raise SystemExit(f"gt dir not found: {GT_DIR}")

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    DOCLING_OUT_ROOT.mkdir(parents=True, exist_ok=True)

    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print("=== Step 1: Generate Docling predictions ===")
    ok, failed = generate_predictions(rows)
    print(f"[PRED] wrote/kept {ok} files, failed={failed} -> {PRED_DIR}")

    print("\n=== Step 2: Evaluate CER/WER ===")
    evaluate_predictions(rows)


if __name__ == "__main__":
    main()