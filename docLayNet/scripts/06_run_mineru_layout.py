from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
PROJECT_ROOT = ROOT.parent                   # .../ocr
SCRIPTS = ROOT / "scripts"
OUTPUTS = ROOT / "outputs"
IMAGES_DIR = OUTPUTS / "images"
MINERU_RAW_DIR = OUTPUTS / "mineru_raw"

# 若你已經有 sample id 清單，優先使用
SAMPLE_CSV_CANDIDATES = [
    OUTPUTS / "gt" / "sample20_ids.csv",
    OUTPUTS / "sample20_ids.csv",
]


def find_mineru_python() -> Path:
    candidates = [
        PROJECT_ROOT / "mineru_eval" / ".venv" / "Scripts" / "python.exe",  # Windows
        PROJECT_ROOT / "mineru_eval" / ".venv" / "bin" / "python",          # Linux/macOS
    ]
    for p in candidates:
        if p.exists():
            return p

    raise SystemExit(
        "MinerU python not found. Expected one of:\n"
        + "\n".join(str(p) for p in candidates)
    )


def load_sample_ids() -> list[str]:
    for csv_path in SAMPLE_CSV_CANDIDATES:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

            if not rows:
                continue

            key_candidates = ["id", "image_id", "doc_id"]
            for key in key_candidates:
                if key in rows[0]:
                    return [r[key].strip() for r in rows if r.get(key, "").strip()]

            raise SystemExit(f"No id column found in {csv_path}")

    # fallback: 直接掃 outputs/images
    ids = sorted(
        p.stem for p in IMAGES_DIR.glob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    if not ids:
        raise SystemExit(
            "No sample id list found, and outputs/images is empty.\n"
            "Please provide sample20_ids.csv or put sampled images under outputs/images/."
        )
    return ids


def find_image_path(doc_id: str) -> Path:
    for ext in (".png", ".jpg", ".jpeg"):
        p = IMAGES_DIR / f"{doc_id}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"Image not found for id={doc_id} under {IMAGES_DIR}")


def main() -> None:
    mineru_python = find_mineru_python()
    infer_script = SCRIPTS / "06a_mineru_infer.py"

    if not infer_script.exists():
        raise SystemExit(f"Missing infer script: {infer_script}")

    doc_ids = load_sample_ids()
    MINERU_RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] MinerU python: {mineru_python}")
    print(f"[INFO] Infer script : {infer_script}")
    print(f"[INFO] Total docs    : {len(doc_ids)}")

    failed: list[str] = []

    for i, doc_id in enumerate(doc_ids, start=1):
        try:
            image_path = find_image_path(doc_id)
        except Exception as e:
            print(f"[FAIL] {doc_id}: {e}")
            failed.append(doc_id)
            continue

        out_dir = MINERU_RAW_DIR / doc_id
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(mineru_python),
            str(infer_script),
            "--input",
            str(image_path),
            "--output_dir",
            str(out_dir),
            "--doc_id",
            doc_id,
        ]

        print(f"[{i}/{len(doc_ids)}] RUN {doc_id}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[FAIL] {doc_id}: returncode={e.returncode}")
            failed.append(doc_id)
        except Exception as e:
            print(f"[FAIL] {doc_id}: {e}")
            failed.append(doc_id)

    print("\n=== MinerU batch inference done ===")
    print(f"total={len(doc_ids)} failed={len(failed)}")

    if failed:
        print("failed ids:")
        for x in failed:
            print(f"  - {x}")
        sys.exit(1)


if __name__ == "__main__":
    main()