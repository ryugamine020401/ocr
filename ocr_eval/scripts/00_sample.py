from __future__ import annotations

import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IMAGES_DIR = DATA / "images"
OCR_GT_DIR = DATA / "ocr_gt"

SAMPLE_LIST = DATA / "sample_list.txt"
MANIFEST = DATA / "manifest.csv"


def main() -> None:
    if not IMAGES_DIR.exists():
        raise SystemExit(f"missing images dir: {IMAGES_DIR}")
    if not OCR_GT_DIR.exists():
        raise SystemExit(f"missing ocr_gt dir: {OCR_GT_DIR}")

    # Collect candidate images (png/jpg/jpeg)
    exts = {".png", ".jpg", ".jpeg", ".JPG", ".JPEG", ".PNG"}
    images = sorted([p for p in IMAGES_DIR.iterdir() if p.is_file() and p.suffix in exts])

    if len(images) < 30:
        raise SystemExit(f"not enough images: {len(images)} (<30)")

    # Reprodu   cible sampling
    seed = 42
    rng = random.Random(seed)
    sample = rng.sample(images, 30)

    # Write sample_list.txt (filenames only)
    SAMPLE_LIST.write_text("\n".join(p.name for p in sample) + "\n", encoding="utf-8")

    # Build manifest.csv
    rows = []
    for img in sample:
        _id = img.stem
        gt_json = OCR_GT_DIR / f"{_id}.json"
        if not gt_json.exists():
            raise SystemExit(f"missing matching OCR JSON for {_id}: {gt_json}")
        rows.append(
            {
                "id": _id,
                "image_path": str(img),
                "ocr_json_path": str(gt_json),
            }
        )

    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "image_path", "ocr_json_path"])
        w.writeheader()
        w.writerows(rows)

    print(f"[OK] sample_list -> {SAMPLE_LIST} (seed={seed}, n=30)")
    print(f"[OK] manifest -> {MANIFEST} (rows={len(rows)})")


if __name__ == "__main__":
    main()