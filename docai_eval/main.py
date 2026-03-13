from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.cloud import documentai as documentai
from jiwer import cer, wer


# =========================
# 路徑設定
# =========================
HERE = Path(__file__).resolve().parent   # OCR/docai_eval
ROOT = HERE.parent                       # OCR
OCR_EVAL_ROOT = ROOT / "ocr_eval"        # OCR/ocr_eval

DATA = OCR_EVAL_ROOT / "data"
MANIFEST = DATA / "manifest.csv"
GT_DIR = DATA / "gt"
PRED_DIR = DATA / "pred" / "document_ai"
OUT_CSV = DATA / "results_document_ai.csv"

# 已有預測時是否跳過，避免重複送 GCP
SKIP_EXISTING_PRED = True


# =========================
# GCP Client
# =========================
def get_client(location: str):
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    return documentai.DocumentProcessorServiceClient(client_options=opts)


# =========================
# 工具函式
# =========================
def normalize_for_eval(s: str) -> str:
    s = s.lower()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    return s.strip()


def resolve_image_path(raw_path: str) -> Path:
    """
    manifest.csv 的 image_path 可能是：
    1. 絕對路徑
    2. 相對於 ocr_eval 的路徑
    3. 相對於 manifest.csv 所在位置(data/) 的路徑

    這裡依序嘗試。
    """
    p = Path(raw_path)

    if p.is_absolute():
        return p.resolve()

    candidates = [
        (OCR_EVAL_ROOT / p).resolve(),
        (DATA / p).resolve(),
    ]

    for c in candidates:
        if c.exists():
            return c

    # 找不到時，回傳第一種推定路徑，方便錯誤訊息直接看
    return candidates[0]


def detect_mime_type(image_path: Path) -> str:
    suf = image_path.suffix.lower()
    if suf == ".png":
        return "image/png"
    if suf in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suf == ".pdf":
        return "application/pdf"
    raise SystemExit(f"unsupported suffix: {image_path.name}")


def load_manifest() -> List[Dict[str, str]]:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")

    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit(f"manifest is empty: {MANIFEST}")

    required_cols = {"id", "image_path"}
    missing = required_cols - set(rows[0].keys())
    if missing:
        raise SystemExit(f"manifest missing columns: {sorted(missing)}")

    return rows


# =========================
# OCR 階段
# =========================
def run_document_ai_ocr(rows: List[Dict[str, str]]) -> None:
    load_dotenv(HERE / ".env")

    project_id = os.getenv("GCP_PROJECT_ID")
    location = os.getenv("GCP_LOCATION", "us")
    processor_id = os.getenv("GCP_OCR_PROCESSOR_ID") or os.getenv("GCP_PROCESSOR_ID")

    if not project_id or not processor_id:
        raise SystemExit(
            "Missing env: GCP_PROJECT_ID and (GCP_OCR_PROCESSOR_ID or GCP_PROCESSOR_ID)"
        )

    PRED_DIR.mkdir(parents=True, exist_ok=True)

    client = get_client(location)
    processor_name = client.processor_path(project_id, location, processor_id)

    total = len(rows)
    done = 0
    skipped = 0

    for i, r in enumerate(rows, start=1):
        _id = r["id"].strip()
        image_path = resolve_image_path(r["image_path"])
        out_path = PRED_DIR / f"{_id}.txt"

        if not image_path.exists():
            raise SystemExit(f"missing image: {image_path}")

        if SKIP_EXISTING_PRED and out_path.exists():
            print(f"[SKIP {i}/{total}] {_id} -> already exists")
            skipped += 1
            continue

        mime = detect_mime_type(image_path)

        print(f"[OCR  {i}/{total}] {_id} -> {image_path.name}")

        raw = documentai.RawDocument(
            content=image_path.read_bytes(),
            mime_type=mime,
        )
        req = documentai.ProcessRequest(
            name=processor_name,
            raw_document=raw,
        )

        resp = client.process_document(request=req, timeout=600)
        text = (resp.document.text or "").strip()

        out_path.write_text(text, encoding="utf-8")
        done += 1

    print(f"[OCR DONE] new={done}, skipped={skipped}, total={total}")
    print(f"[OCR OUT] {PRED_DIR}")


# =========================
# 評估階段
# =========================
def evaluate_document_ai(rows: List[Dict[str, str]]) -> None:
    if not GT_DIR.exists():
        raise SystemExit(f"gt dir not found: {GT_DIR}")
    if not PRED_DIR.exists():
        raise SystemExit(f"pred dir not found: {PRED_DIR}")

    results = []
    cer_list = []
    wer_list = []

    for i, r in enumerate(rows, start=1):
        _id = r["id"].strip()
        gt_path = GT_DIR / f"{_id}.txt"
        pred_path = PRED_DIR / f"{_id}.txt"

        if not gt_path.exists():
            raise SystemExit(f"missing gt: {gt_path}")
        if not pred_path.exists():
            raise SystemExit(f"missing pred: {pred_path}")

        gt = normalize_for_eval(
            gt_path.read_text(encoding="utf-8-sig", errors="ignore")
        )
        pred = normalize_for_eval(
            pred_path.read_text(encoding="utf-8-sig", errors="ignore")
        )

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

        print(f"[EVAL {i}/{len(rows)}] {_id}  CER={c:.6f}  WER={w:.6f}")

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


# =========================
# main
# =========================
def main() -> None:
    rows = load_manifest()
    run_document_ai_ocr(rows)
    evaluate_document_ai(rows)


if __name__ == "__main__":
    main()