from __future__ import annotations

import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

IMAGES_DIR = ROOT / "outputs" / "images"
RAW_DIR = ROOT / "outputs" / "docling_raw"

# docLayNet 的同層兄弟資料夾：ocr/docling_eval/.venv
DOC_PYTHON = ROOT.parent / "docling_eval" / ".venv" / "Scripts" / "python.exe"
DOC_SCRIPT = SCRIPT_DIR / "06a_docling_infer.py"

MAX_IMAGES = 30


def main() -> None:
    if not IMAGES_DIR.exists():
        raise SystemExit(f"Images dir not found: {IMAGES_DIR}")
    if not DOC_PYTHON.exists():
        raise SystemExit(f"Docling python not found: {DOC_PYTHON}")
    if not DOC_SCRIPT.exists():
        raise SystemExit(f"Docling infer script not found: {DOC_SCRIPT}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(IMAGES_DIR.glob("*.png"))[:MAX_IMAGES]

    print(f"[INFO] images dir: {IMAGES_DIR}")
    print(f"[INFO] output dir: {RAW_DIR}")
    print(f"[INFO] doc python: {DOC_PYTHON}")
    print(f"[INFO] doc script: {DOC_SCRIPT}")
    print(f"[INFO] num images: {len(images)}")

    for img in images:
        out_dir = RAW_DIR / img.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"{img.stem}.json"

        cmd = [
            str(DOC_PYTHON),
            str(DOC_SCRIPT),
            str(img),
            str(out_json),
        ]

        print(f"\n[RUN] {img.name}")
        subprocess.run(cmd, check=True)

    print("\n[OK] all images processed")


if __name__ == "__main__":
    main()