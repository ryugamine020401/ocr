from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "paddle_raw"
OUT_DIR = ROOT / "outputs" / "pred"
OUT_FILE = OUT_DIR / "pred_paddle_sample30.json"

MAX_IMAGES = 30

# 先全部當成 text 類別
# 如果你的 GT categories 裡 text 對應不是 1，要再改這裡
CATEGORY_ID = 1


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def xyxy_to_xywh(bbox: list[float]) -> list[float] | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None

    x1, y1, x2, y2 = bbox

    x1 = float(x1)
    y1 = float(y1)
    x2 = float(x2)
    y2 = float(y2)

    w = x2 - x1
    h = y2 - y1

    if w <= 0 or h <= 0:
        return None

    return [x1, y1, w, h]


def parse_image_id(path: Path) -> int | None:
    try:
        return int(path.stem)
    except ValueError:
        return None


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"Paddle raw dir not found: {RAW_DIR}")

    json_paths = sorted(RAW_DIR.glob("*/*.json"))[:MAX_IMAGES]
    if not json_paths:
        raise SystemExit(f"No json files found under: {RAW_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    predictions = []
    scanned_files = 0
    skipped_files = 0
    skipped_blocks = 0

    for json_path in json_paths:
        image_id = parse_image_id(json_path)
        if image_id is None:
            print(f"[WARN] skip {json_path}: image_id is not numeric")
            skipped_files += 1
            continue

        try:
            data = load_json(json_path)
        except Exception as e:
            print(f"[WARN] skip {json_path}: failed to read json: {e}")
            skipped_files += 1
            continue

        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            print(f"[WARN] skip {json_path}: 'blocks' is not a list")
            skipped_files += 1
            continue

        scanned_files += 1

        valid_count = 0

        for block in blocks:
            if not isinstance(block, dict):
                skipped_blocks += 1
                continue

            block_type = block.get("type")
            if block_type != "text":
                skipped_blocks += 1
                continue

            bbox = block.get("bbox")
            coco_bbox = xyxy_to_xywh(bbox)
            if coco_bbox is None:
                skipped_blocks += 1
                continue

            score = block.get("score", 1.0)
            try:
                score = float(score)
            except Exception:
                score = 1.0

            pred = {
                "image_id": image_id,
                "category_id": CATEGORY_ID,
                "bbox": coco_bbox,
                "score": score,
            }
            predictions.append(pred)
            valid_count += 1

        print(f"[OK] {json_path.name}: valid_predictions={valid_count}")

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"[OK] scanned files     : {scanned_files}")
    print(f"[OK] skipped files     : {skipped_files}")
    print(f"[OK] skipped blocks    : {skipped_blocks}")
    print(f"[OK] total predictions : {len(predictions)}")
    print(f"[OK] saved to          : {OUT_FILE}")


if __name__ == "__main__":
    main()