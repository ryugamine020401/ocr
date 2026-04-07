from __future__ import annotations

import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

IMAGES_DIR = ROOT / "outputs" / "images"
RAW_DIR = ROOT / "outputs" / "paddle_raw"

# ✅ 指向 ocr_eval 的虛擬環境
OCR_PYTHON = ROOT.parent / "ocr_eval" / ".venv" / "Scripts" / "python.exe"
OCR_SCRIPT = SCRIPT_DIR / "06a_paddle_infer.py"

MAX_IMAGES = 30


def main() -> None:
    if not IMAGES_DIR.exists():
        raise SystemExit(f"Images dir not found: {IMAGES_DIR}")
    if not OCR_PYTHON.exists():
        raise SystemExit(f"OCR python not found: {OCR_PYTHON}")
    if not OCR_SCRIPT.exists():
        raise SystemExit(f"OCR infer script not found: {OCR_SCRIPT}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(IMAGES_DIR.glob("*.png"))[:MAX_IMAGES]

    print(f"[INFO] images dir: {IMAGES_DIR}")
    print(f"[INFO] output dir: {RAW_DIR}")
    print(f"[INFO] ocr python: {OCR_PYTHON}")
    print(f"[INFO] ocr script: {OCR_SCRIPT}")
    print(f"[INFO] num images: {len(images)}")

    for img in images:
        out_dir = RAW_DIR / img.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"{img.stem}.json"

        cmd = [
            str(OCR_PYTHON),
            str(OCR_SCRIPT),
            str(img),
            str(out_json),
        ]

        print(f"\n[RUN] {img.name}")
        subprocess.run(cmd, check=True)

    print("\n[OK] all images processed")


if __name__ == "__main__":
    main()