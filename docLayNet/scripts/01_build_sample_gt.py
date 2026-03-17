from __future__ import annotations

import json
import os
from pathlib import Path

from datasets import load_dataset


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATASETS_DIR = ROOT / "datasets"
OUTPUT_GT_DIR = ROOT / "outputs" / "gt"

os.environ["HF_DATASETS_CACHE"] = str(DATASETS_DIR)

# 改用標準格式版本，不要再用舊的 docling-project/DocLayNet
DATASET_NAME = "docling-project/DocLayNet-v1.1"
SPLIT = "train"
SAMPLE_SIZE = 30
OUT_FILE = OUTPUT_GT_DIR / f"gt_5class_sample{SAMPLE_SIZE}.json"

# v1.1 / v1.2 類別定義：
# 1 Caption
# 2 Footnote
# 3 Formula
# 4 List-item
# 5 Page-footer
# 6 Page-header
# 7 Picture
# 8 Section-header
# 9 Table
# 10 Text
# 11 Title
DOCLAYNET_TO_TARGET = {
    7: 0,   # Picture
    8: 1,   # Section-header
    9: 2,   # Table
    10: 3,  # Text
    11: 4,  # Title
}

TARGET_CATEGORIES = [
    {"id": 0, "name": "Picture"},
    {"id": 1, "name": "Section-header"},
    {"id": 2, "name": "Table"},
    {"id": 3, "name": "Text"},
    {"id": 4, "name": "Title"},
]


def build_coco_gt(split: str, sample_size: int) -> dict:
    ds = load_dataset(
        DATASET_NAME,
        split=split,
        download_mode="reuse_dataset_if_exists",
    )

    if sample_size > len(ds):
        raise ValueError(f"sample_size={sample_size} > dataset size={len(ds)}")

    subset = ds.select(range(sample_size))

    images = []
    annotations = []
    ann_id = 0

    for i, sample in enumerate(subset):
        image_id = i

        pil_image = sample["image"]
        width, height = pil_image.size

        metadata = sample.get("metadata", {})
        file_stem = (
            metadata.get("image_id")
            or metadata.get("page_hash")
            or f"sample_{i:05d}"
        )

        images.append({
            "id": image_id,
            "file_name": f"{file_stem}.png",
            "width": width,
            "height": height,
        })

        bboxes = sample["bboxes"]
        category_ids = sample["category_id"]
        areas = sample.get("area")

        for j, (bbox, cid) in enumerate(zip(bboxes, category_ids)):
            if cid not in DOCLAYNET_TO_TARGET:
                continue

            if areas is not None:
                area = areas[j]
            else:
                area = float(bbox[2]) * float(bbox[3])

            annotations.append({
                "id": ann_id,
                "image_id": image_id,
                "category_id": DOCLAYNET_TO_TARGET[cid],
                "bbox": [float(x) for x in bbox],   # [x, y, w, h]
                "area": float(area),
                "iscrowd": 0,
            })
            ann_id += 1

    coco_gt = {
        "images": images,
        "annotations": annotations,
        "categories": TARGET_CATEGORIES,
    }
    return coco_gt


def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_GT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] project root: {ROOT}")
    print(f"[INFO] datasets dir: {DATASETS_DIR}")
    print(f"[INFO] output file : {OUT_FILE}")
    print(f"[INFO] dataset     : {DATASET_NAME}")
    print(f"[INFO] loading split={SPLIT!r}, sample_size={SAMPLE_SIZE}")

    coco_gt = build_coco_gt(split=SPLIT, sample_size=SAMPLE_SIZE)

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(coco_gt, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {OUT_FILE}")
    print(f"[OK] num_images: {len(coco_gt['images'])}")
    print(f"[OK] num_annotations: {len(coco_gt['annotations'])}")


if __name__ == "__main__":
    main()