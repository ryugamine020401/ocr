from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = DATA / "manifest.csv"
GT_DIR = DATA / "gt"
GT_SUMMARY = DATA / "gt_summary.csv"


def extract_text_msocr(obj: dict) -> str:
    """
    Microsoft OCR format observed:
      {
        "status": "...",
        "recognitionResults": [
          {
            "lines": [
              {
                "text": "...",           # sometimes present
                "words": [{"text": "..."}]  # fallback
              }
            ]
          }
        ]
      }
    """
    lines_out: list[str] = []

    for rr in obj.get("recognitionResults", []) or []:
        for line in rr.get("lines", []) or []:
            # Prefer line-level text if available
            t = line.get("text")
            if isinstance(t, str) and t.strip():
                lines_out.append(t)
                continue

            # Otherwise, join words
            words = line.get("words", []) or []
            toks = []
            for w in words:
                wt = w.get("text")
                if isinstance(wt, str) and wt.strip():
                    toks.append(wt)
            if toks:
                lines_out.append(" ".join(toks))

    # Normalize: trim line ends, keep newlines, remove leading/trailing blank
    text = "\n".join(s.rstrip() for s in lines_out).strip()
    return text


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")

    GT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "ocr_json_path"}
        if not required.issubset(reader.fieldnames or []):
            raise SystemExit(f"manifest missing columns: {required} (got {reader.fieldnames})")
        for r in reader:
            rows.append(r)

    summary = []

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

        summary.append(
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
        writer.writerows(summary)

    print(f"[OK] wrote {len(summary)} gt txt files -> {GT_DIR}")
    print(f"[OK] summary -> {GT_SUMMARY}")


if __name__ == "__main__":
    main()