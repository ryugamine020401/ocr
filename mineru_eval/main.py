from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from jiwer import cer, wer


# ========= 路徑設定 =========
HERE = Path(__file__).resolve().parent
OCR_EVAL_ROOT = (HERE.parent / "ocr_eval").resolve()

DATA = OCR_EVAL_ROOT / "data"
MANIFEST = DATA / "manifest.csv"
GT_DIR = DATA / "gt"
PRED_DIR = DATA / "pred" / "mineru"
OUT_CSV = DATA / "results_mineru.csv"

TMP_ROOT = HERE / "tmp_mineru_pipeline"
PDF_DIR = TMP_ROOT / "pdf_single"
MINERU_RAW_OUT_ROOT = TMP_ROOT / "out_mineru_raw"


# ========= 工具函式 =========
def clear_dir_files(dir_path: Path, pattern: str = "*") -> int:
    """
    清掉某資料夾底下符合 pattern 的直接檔案，不遞迴。
    """
    if not dir_path.exists():
        return 0

    removed = 0
    for p in dir_path.glob(pattern):
        if p.is_file():
            p.unlink()
            removed += 1
    return removed


def clear_dir_tree(dir_path: Path) -> int:
    """
    整個資料夾刪掉重建，用於 MinerU raw output 這種暫存。
    """
    if not dir_path.exists():
        return 0
    shutil.rmtree(dir_path)
    return 1


def load_manifest_rows(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit(f"manifest is empty: {manifest_path}")

    return rows


def resolve_image_path(raw_path: str) -> Path:
    """
    manifest 裡的 image_path 可能是相對路徑，也可能是絕對路徑。
    這裡統一解析。
    """
    p = Path(raw_path.strip())
    if p.is_absolute():
        return p

    return (OCR_EVAL_ROOT / p).resolve()


def image_to_single_page_pdf(image_path: Path, out_pdf: Path) -> None:
    """
    單張圖片轉單頁 PDF。
    """
    im = Image.open(image_path)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_pdf, "PDF", resolution=300.0)


def md_to_text(md: str) -> str:
    """
    保守型 Markdown 清洗。
    """
    s = md

    s = re.sub(r"```.*?```", " ", s, flags=re.DOTALL)
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"^[>#\-\*\+\s]+", "", s, flags=re.MULTILINE)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


def normalize_for_eval(s: str) -> str:
    s = s.lower()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n", " ")
    s = " ".join(s.split())
    return s.strip()


def resolve_mineru_executable() -> str:
    """
    優先使用目前 Python 環境旁邊的 mineru.exe。
    找不到時再退回 PATH 搜尋。
    """
    candidate = Path(sys.executable).parent / "mineru.exe"
    if candidate.exists():
        return str(candidate)

    mineru_exe = shutil.which("mineru")
    if mineru_exe:
        return mineru_exe

    raise FileNotFoundError(
        "Cannot find MinerU executable.\n"
        f"sys.executable = {sys.executable}\n"
        f"expected nearby exe = {candidate}\n"
        "PATH lookup for 'mineru' also failed."
    )


def run_mineru(input_path: Path, out_dir: Path, backend: str, method: str, lang: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    mineru_exe = resolve_mineru_executable()

    cmd = [
        mineru_exe,
        "-p",
        str(input_path),
        "-o",
        str(out_dir),
        "-b",
        backend,
        "-m",
        method,
        "-l",
        lang,
    ]

    print(f"[DEBUG] sys.executable = {sys.executable}")
    print(f"[DEBUG] mineru_exe    = {mineru_exe}")
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def find_first_md(out_dir: Path) -> Path:
    mds = sorted(out_dir.rglob("*.md"))
    if not mds:
        raise FileNotFoundError(f"MinerU output has no .md under: {out_dir}")
    return mds[0]


# ========= Step 1: 圖片轉 PDF =========
def step_make_pdfs(rows: list[dict]) -> int:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    removed = clear_dir_files(PDF_DIR, "*.pdf")

    created = 0
    for r in rows:
        _id = (r.get("id") or "").strip()
        raw_image_path = (r.get("image_path") or "").strip()

        if not _id:
            print("[WARN] missing id, skip pdf step")
            continue

        image_path = resolve_image_path(raw_image_path)
        if not image_path.exists():
            raise SystemExit(f"missing image: {image_path}")

        out_pdf = PDF_DIR / f"{_id}.pdf"
        image_to_single_page_pdf(image_path, out_pdf)
        created += 1

    print(f"[OK] cleared {removed} old PDFs from -> {PDF_DIR}")
    print(f"[OK] wrote {created} single-page PDFs -> {PDF_DIR}")
    return created


# ========= Step 2: 跑 MinerU =========
def step_run_mineru(rows: list[dict]) -> tuple[int, int]:
    PRED_DIR.mkdir(parents=True, exist_ok=True)

    removed_pred = clear_dir_files(PRED_DIR, "*")
    raw_removed = clear_dir_tree(MINERU_RAW_OUT_ROOT)

    MINERU_RAW_OUT_ROOT.mkdir(parents=True, exist_ok=True)

    backend = os.getenv("MINERU_BACKEND", "pipeline")
    method = os.getenv("MINERU_METHOD", "ocr")
    lang = os.getenv("MINERU_LANG", "en")

    print(f"[INFO] MINERU_BACKEND={backend}")
    print(f"[INFO] MINERU_METHOD={method}")
    print(f"[INFO] MINERU_LANG={lang}")
    print(f"[INFO] cleared {removed_pred} old files from -> {PRED_DIR}")
    if raw_removed:
        print(f"[INFO] reset raw mineru dir -> {MINERU_RAW_OUT_ROOT}")

    ok = 0
    failed = 0

    for r in rows:
        _id = (r.get("id") or "").strip()
        if not _id:
            print("[WARN] missing id, skip mineru step")
            continue

        pdf_path = PDF_DIR / f"{_id}.pdf"
        if not pdf_path.exists():
            raise SystemExit(f"missing generated pdf: {pdf_path}")

        per_file_out = MINERU_RAW_OUT_ROOT / _id
        out_txt = PRED_DIR / f"{_id}.txt"

        try:
            print(f"[MinerU] {_id} ...")
            run_mineru(
                input_path=pdf_path,
                out_dir=per_file_out,
                backend=backend,
                method=method,
                lang=lang,
            )

            md_path = find_first_md(per_file_out)
            md = md_path.read_text(encoding="utf-8", errors="replace")
            text = md_to_text(md)

            out_txt.write_text(text, encoding="utf-8")
            ok += 1

        except Exception as e:
            failed += 1
            err_path = PRED_DIR / f"{_id}.error.txt"
            err_path.write_text(str(e), encoding="utf-8")
            print(f"[FAIL] {_id}: {e}")

    print(f"[OK] MinerU wrote {ok} txt files, failed={failed} -> {PRED_DIR}")
    return ok, failed


# ========= Step 3: 評估 =========
def step_evaluate(rows: list[dict]) -> None:
    if not GT_DIR.exists():
        raise SystemExit(f"gt dir not found: {GT_DIR}")
    if not PRED_DIR.exists():
        raise SystemExit(f"pred dir not found: {PRED_DIR}")

    results = []
    cer_list = []
    wer_list = []

    for r in rows:
        _id = (r.get("id") or "").strip()
        if not _id:
            continue

        gt_path = GT_DIR / f"{_id}.txt"
        pred_path = PRED_DIR / f"{_id}.txt"

        if not gt_path.exists():
            raise SystemExit(f"missing gt: {gt_path}")
        if not pred_path.exists():
            print(f"[WARN] missing pred, skip eval: {pred_path}")
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
        raise SystemExit("no evaluation results generated")

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
    print("=== USING UPDATED main.py ===")

    rows = load_manifest_rows(MANIFEST)

    print(f"[INFO] OCR_EVAL_ROOT = {OCR_EVAL_ROOT}")
    print(f"[INFO] MANIFEST      = {MANIFEST}")
    print(f"[INFO] GT_DIR        = {GT_DIR}")
    print(f"[INFO] PRED_DIR      = {PRED_DIR}")
    print(f"[INFO] TMP PDF DIR   = {PDF_DIR}")
    print(f"[INFO] TMP RAW DIR   = {MINERU_RAW_OUT_ROOT}")

    step_make_pdfs(rows)
    ok, failed = step_run_mineru(rows)

    if ok == 0:
        raise SystemExit(
            "MinerU produced 0 prediction files. "
            "Please check MinerU installation / executable path."
        )

    step_evaluate(rows)


if __name__ == "__main__":
    main()