from __future__ import annotations

import os
from pathlib import Path

from datasets import load_dataset


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATASETS_DIR = ROOT / "datasets"
OUTPUT_IMG_DIR = ROOT / "outputs" / "images"

os.environ["HF_DATASETS_CACHE"] = str(DATASETS_DIR)

DATASET_NAME = "docling-project/DocLayNet-v1.1"
SPLIT = "train"
SAMPLE_SIZE = 30


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_IMG_DIR.mkdir(parents=True, exist_ok=True)

    ds = load_dataset(
        DATASET_NAME,
        split=SPLIT,
        download_mode="reuse_dataset_if_exists",
    )

    subset = ds.select(range(SAMPLE_SIZE))

    for i, sample in enumerate(subset):
        image = sample["image"]
        metadata = sample.get("metadata", {})

        file_stem = (
            metadata.get("image_id")
            or metadata.get("page_hash")
            or f"sample_{i:05d}"
        )

        out_path = OUTPUT_IMG_DIR / f"{file_stem}.png"
        image.save(out_path)

        print(f"[OK] saved: {out_path}")

    print(f"[OK] exported {SAMPLE_SIZE} images to: {OUTPUT_IMG_DIR}")


if __name__ == "__main__":
    main()