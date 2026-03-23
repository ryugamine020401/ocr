from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
OUTPUTS = ROOT / "outputs"
RAW_DIR = OUTPUTS / "mineru_raw"
GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
OUT_JSON = OUTPUTS / "pred" / "pred_mineru_sample30.json"

CATEGORY_NAME_TO_ID = {
    "Picture": 0,
    "Section-header": 1,
    "Table": 2,
    "Text": 3,
    "Title": 4,
}

MINERU_TYPE_TO_TARGET = {
    "image": "Picture",
    "table": "Table",
    "text": "Text",
    "header": "Section-header",
}

SHIFT_X = 15
SHIFT_Y = 15


def load_gt_image_info() -> dict[str, dict[str, Any]]:
    gt = json.loads(GT_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}

    for im in gt["images"]:
        stem = Path(im["file_name"]).stem
        out[stem] = {
            "image_id": im["id"],
            "width": float(im["width"]),
            "height": float(im["height"]),
        }

    return out


def is_valid_bbox(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    return all(isinstance(v, (int, float)) for v in bbox)


def xyxy_to_xywh(bbox: list[float]) -> list[float]:
    x1, y1, x2, y2 = bbox
    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    return [x, y, w, h]


def scale_bbox_if_needed(
    bbox: list[float],
    image_width: float,
    image_height: float,
) -> list[float]:
    """
    若 bbox 是 normalized (0~1)，就乘回原圖尺寸；
    否則直接視為 pixel xyxy。
    """
    x1, y1, x2, y2 = [float(v) for v in bbox]

    if max(x1, y1, x2, y2) <= 1.5:
        x1 *= image_width
        x2 *= image_width
        y1 *= image_height
        y2 *= image_height

    return [x1, y1, x2, y2]


def apply_shift_xyxy(bbox: list[float], shift_x: float, shift_y: float) -> list[float]:
    x1, y1, x2, y2 = bbox
    return [
        x1 + shift_x,
        y1 + shift_y,
        x2 + shift_x,
        y2 + shift_y,
    ]


def unwrap_blocks(data: Any) -> list[dict[str, Any]]:
    """
    MinerU 目前可能有：
    1. root = [ {...}, {...} ]
    2. root = [ [ {...}, {...} ] ]
    """
    if not isinstance(data, list):
        return []

    if all(isinstance(x, dict) for x in data):
        return data

    if len(data) == 1 and isinstance(data[0], list):
        inner = data[0]
        if all(isinstance(x, dict) for x in inner):
            return inner

    blocks: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            blocks.append(item)
        elif isinstance(item, list):
            for sub in item:
                if isinstance(sub, dict):
                    blocks.append(sub)
    return blocks


def iter_primary_json_files() -> list[Path]:
    """
    只讀 outputs/mineru_raw/<id>/<id>.json
    不讀 _tmp 裡的其他中間 json。
    """
    files: list[Path] = []
    for subdir in sorted(RAW_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        candidate = subdir / f"{subdir.name}.json"
        if candidate.exists():
            files.append(candidate)
    return files


def main() -> None:
    if not GT_JSON.exists():
        raise SystemExit(f"Missing GT json: {GT_JSON}")

    image_info_map = load_gt_image_info()
    json_files = iter_primary_json_files()

    if not json_files:
        raise SystemExit(f"No primary json found under {RAW_DIR}")

    preds: list[dict[str, Any]] = []

    total_blocks = 0
    used_blocks = 0
    skipped_unknown_type = 0
    skipped_bad_bbox = 0
    skipped_missing_image_id = 0

    type_counter: dict[str, int] = {}

    print(f"[INFO] primary json files = {len(json_files)}")
    print(f"[INFO] apply shift: SHIFT_X={SHIFT_X}, SHIFT_Y={SHIFT_Y}")

    for jf in json_files:
        doc_id = jf.stem
        image_info = image_info_map.get(doc_id)

        if image_info is None:
            print(f"[WARN] skip {doc_id}: not found in GT images")
            skipped_missing_image_id += 1
            continue

        image_id = image_info["image_id"]
        image_width = image_info["width"]
        image_height = image_info["height"]

        data = json.loads(jf.read_text(encoding="utf-8"))
        blocks = unwrap_blocks(data)

        if not blocks:
            print(f"[WARN] skip {jf}: no valid blocks found")
            continue

        for block in blocks:
            total_blocks += 1

            if not isinstance(block, dict):
                continue

            raw_type = block.get("type")
            if not isinstance(raw_type, str):
                skipped_unknown_type += 1
                continue

            raw_type = raw_type.strip().lower()
            type_counter[raw_type] = type_counter.get(raw_type, 0) + 1

            target_name = MINERU_TYPE_TO_TARGET.get(raw_type)
            if target_name is None:
                skipped_unknown_type += 1
                continue

            bbox = block.get("bbox")
            if not is_valid_bbox(bbox):
                skipped_bad_bbox += 1
                continue

            bbox_xyxy = scale_bbox_if_needed(
                bbox=[float(v) for v in bbox],
                image_width=image_width,
                image_height=image_height,
            )

            bbox_xyxy = apply_shift_xyxy(
                bbox=bbox_xyxy,
                shift_x=SHIFT_X,
                shift_y=SHIFT_Y,
            )

            coco_bbox = xyxy_to_xywh(bbox_xyxy)
            x, y, w, h = coco_bbox

            if w <= 0 or h <= 0:
                skipped_bad_bbox += 1
                continue

            preds.append(
                {
                    "image_id": image_id,
                    "category_id": CATEGORY_NAME_TO_ID[target_name],
                    "bbox": [x, y, w, h],
                    "score": 1.0,
                }
            )
            used_blocks += 1

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(f"[OK] overwritten: {OUT_JSON}")
    print(f"[INFO] total primary json files : {len(json_files)}")
    print(f"[INFO] total blocks            : {total_blocks}")
    print(f"[INFO] used blocks             : {used_blocks}")
    print(f"[INFO] skipped unknown type    : {skipped_unknown_type}")
    print(f"[INFO] skipped bad bbox        : {skipped_bad_bbox}")
    print(f"[INFO] skipped missing imageid : {skipped_missing_image_id}")
    print(f"[INFO] total predictions       : {len(preds)}")

    print("\n=== USED OUTER TYPES FROM PRIMARY JSON ===")
    for k in sorted(type_counter):
        print(f"{k:15s}: {type_counter[k]}")


if __name__ == "__main__":
    main()