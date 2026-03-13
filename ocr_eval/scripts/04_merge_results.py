from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

TESS = DATA / "results_tesseract.csv"
PADDLE = DATA / "results_paddle.csv"
DOCAI = DATA / "results_document_ai.csv"
MINERU = DATA / "results_mineru.csv"
DOCLING = DATA / "results_docling.csv"

OUT = DATA / "results_merged.csv"
OUT_SUMMARY = DATA / "results_summary.txt"


def read_results(path: Path, model: str) -> dict[str, dict[str, float]]:
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    out: dict[str, dict[str, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            _id = r["id"].strip()
            out[_id] = {
                f"{model}_cer": float(r["cer"]),
                f"{model}_wer": float(r["wer"]),
            }
    return out


def avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def worst_top_k(rows: list[dict], key: str, k: int = 5) -> list[dict]:
    return sorted(
        [r for r in rows if r.get(key) is not None],
        key=lambda r: r[key],
        reverse=True,
    )[:k]


def fmt_score(v: float | None) -> str:
    return f"{v:.6f}" if v is not None else "nan"


def format_compare_line(r: dict, focus_label: str, focus_key: str) -> str:
    model_order = [
        ("tess", "tesseract_cer"),
        ("paddle", "paddle_cer"),
        ("docai", "document_ai_cer"),
        ("mineru", "mineru_cer"),
        ("docling", "docling_cer"),
    ]

    parts = [f"{focus_label}={fmt_score(r.get(focus_key))}"]
    for label, key in model_order:
        if key == focus_key:
            continue
        parts.append(f"{label}_cer={fmt_score(r.get(key))}")

    return f'  {r["id"]}: ' + " ".join(parts)


def main() -> None:
    t = read_results(TESS, "tesseract")
    p = read_results(PADDLE, "paddle")
    d = read_results(DOCAI, "document_ai")
    m = read_results(MINERU, "mineru")
    dl = read_results(DOCLING, "docling")

    ids = sorted(set(t.keys()) | set(p.keys()) | set(d.keys()) | set(m.keys()) | set(dl.keys()))

    rows = []
    for _id in ids:
        row = {"id": _id}
        row.update(t.get(_id, {"tesseract_cer": None, "tesseract_wer": None}))
        row.update(p.get(_id, {"paddle_cer": None, "paddle_wer": None}))
        row.update(d.get(_id, {"document_ai_cer": None, "document_ai_wer": None}))
        row.update(m.get(_id, {"mineru_cer": None, "mineru_wer": None}))
        row.update(dl.get(_id, {"docling_cer": None, "docling_wer": None}))

        # best model by CER (lower is better)
        candidates = []
        if row.get("tesseract_cer") is not None:
            candidates.append(("tesseract", row["tesseract_cer"]))
        if row.get("paddle_cer") is not None:
            candidates.append(("paddle", row["paddle_cer"]))
        if row.get("document_ai_cer") is not None:
            candidates.append(("document_ai", row["document_ai_cer"]))
        if row.get("mineru_cer") is not None:
            candidates.append(("mineru", row["mineru_cer"]))
        if row.get("docling_cer") is not None:
            candidates.append(("docling", row["docling_cer"]))

        candidates.sort(key=lambda x: x[1])
        row["best_model_by_cer"] = candidates[0][0] if candidates else ""
        row["best_cer"] = candidates[0][1] if candidates else None

        rows.append(row)

    # write merged csv
    fields = [
        "id",
        "tesseract_cer", "tesseract_wer",
        "paddle_cer", "paddle_wer",
        "document_ai_cer", "document_ai_wer",
        "mineru_cer", "mineru_wer",
        "docling_cer", "docling_wer",
        "best_model_by_cer", "best_cer",
    ]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # summary values
    t_cer = [r["tesseract_cer"] for r in rows if r["tesseract_cer"] is not None]
    t_wer = [r["tesseract_wer"] for r in rows if r["tesseract_wer"] is not None]

    p_cer = [r["paddle_cer"] for r in rows if r["paddle_cer"] is not None]
    p_wer = [r["paddle_wer"] for r in rows if r["paddle_wer"] is not None]

    d_cer = [r["document_ai_cer"] for r in rows if r["document_ai_cer"] is not None]
    d_wer = [r["document_ai_wer"] for r in rows if r["document_ai_wer"] is not None]

    m_cer = [r["mineru_cer"] for r in rows if r["mineru_cer"] is not None]
    m_wer = [r["mineru_wer"] for r in rows if r["mineru_wer"] is not None]

    dl_cer = [r["docling_cer"] for r in rows if r["docling_cer"] is not None]
    dl_wer = [r["docling_wer"] for r in rows if r["docling_wer"] is not None]

    # counts of best model
    counts = {
        "tesseract": 0,
        "paddle": 0,
        "document_ai": 0,
        "mineru": 0,
        "docling": 0,
    }
    for r in rows:
        bm = r.get("best_model_by_cer")
        if bm in counts:
            counts[bm] += 1

    # worst 5 by each model CER
    worst_by_tess = worst_top_k(rows, "tesseract_cer", 5)
    worst_by_paddle = worst_top_k(rows, "paddle_cer", 5)
    worst_by_docai = worst_top_k(rows, "document_ai_cer", 5)
    worst_by_mineru = worst_top_k(rows, "mineru_cer", 5)
    worst_by_docling = worst_top_k(rows, "docling_cer", 5)

    text = []
    text.append("=== OCR Benchmark Summary (n={}) ===".format(len(rows)))
    text.append("")
    text.append("AVG:")
    text.append("  Tesseract   CER={:.6f}  WER={:.6f}".format(avg(t_cer), avg(t_wer)))
    text.append("  PaddleOCR   CER={:.6f}  WER={:.6f}".format(avg(p_cer), avg(p_wer)))
    text.append("  DocumentAI  CER={:.6f}  WER={:.6f}".format(avg(d_cer), avg(d_wer)))
    text.append("  MinerU      CER={:.6f}  WER={:.6f}".format(avg(m_cer), avg(m_wer)))
    text.append("  Docling     CER={:.6f}  WER={:.6f}".format(avg(dl_cer), avg(dl_wer)))
    text.append("")
    text.append("Best model by CER (count):")
    text.append("  Tesseract   {}".format(counts["tesseract"]))
    text.append("  PaddleOCR   {}".format(counts["paddle"]))
    text.append("  DocumentAI  {}".format(counts["document_ai"]))
    text.append("  MinerU      {}".format(counts["mineru"]))
    text.append("  Docling     {}".format(counts["docling"]))
    text.append("")

    text.append("Worst 5 by Tesseract CER:")
    for r in worst_by_tess:
        text.append(format_compare_line(r, "tess_cer", "tesseract_cer"))

    text.append("")
    text.append("Worst 5 by PaddleOCR CER:")
    for r in worst_by_paddle:
        text.append(format_compare_line(r, "paddle_cer", "paddle_cer"))

    text.append("")
    text.append("Worst 5 by DocumentAI CER:")
    for r in worst_by_docai:
        text.append(format_compare_line(r, "docai_cer", "document_ai_cer"))

    text.append("")
    text.append("Worst 5 by MinerU CER:")
    for r in worst_by_mineru:
        text.append(format_compare_line(r, "mineru_cer", "mineru_cer"))

    text.append("")
    text.append("Worst 5 by Docling CER:")
    for r in worst_by_docling:
        text.append(format_compare_line(r, "docling_cer", "docling_cer"))

    OUT_SUMMARY.write_text("\n".join(text) + "\n", encoding="utf-8")

    print(f"[OK] merged -> {OUT}")
    print(f"[OK] summary -> {OUT_SUMMARY}")


if __name__ == "__main__":
    main()