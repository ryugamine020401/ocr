# from __future__ import annotations

# import json
# from pathlib import Path
# from typing import Any


# ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
# OUTPUTS = ROOT / "outputs"
# RAW_DIR = OUTPUTS / "mineru_raw"
# GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
# OUT_JSON = OUTPUTS / "pred" / "pred_mineru_sample30.json"

# CATEGORY_NAME_TO_ID = {
#     "Picture": 0,
#     "Section-header": 1,
#     "Table": 2,
#     "Text": 3,
#     "Title": 4,
# }

# MINERU_TYPE_TO_TARGET = {
#     "image": "Picture",
#     "table": "Table",
#     "table_body": "Table",
#     "table_caption": "Text",
#     "table_footnote": "Text",
#     "text": "Text",
#     "list": "Text",
#     "title": "Title",
# }

# SHIFT_X = 0
# SHIFT_Y = 0


# def load_gt_image_info() -> dict[str, dict[str, Any]]:
#     gt = json.loads(GT_JSON.read_text(encoding="utf-8"))
#     out: dict[str, dict[str, Any]] = {}

#     for im in gt["images"]:
#         stem = Path(im["file_name"]).stem
#         out[stem] = {
#             "image_id": im["id"],
#             "width": float(im["width"]),
#             "height": float(im["height"]),
#         }

#     return out


# def is_valid_bbox(bbox: Any) -> bool:
#     if not isinstance(bbox, list) or len(bbox) != 4:
#         return False

#     try:
#         x1, y1, x2, y2 = [float(v) for v in bbox]
#     except Exception:
#         return False

#     return x2 > x1 and y2 > y1


# def xyxy_to_xywh(bbox: list[float]) -> list[float]:
#     x1, y1, x2, y2 = bbox
#     return [x1, y1, x2 - x1, y2 - y1]


# def scale_bbox_if_needed(
#     bbox: list[float],
#     image_width: float,
#     image_height: float,
# ) -> list[float]:
#     x1, y1, x2, y2 = [float(v) for v in bbox]

#     if max(x1, y1, x2, y2) <= 1.5:
#         x1 *= image_width
#         x2 *= image_width
#         y1 *= image_height
#         y2 *= image_height

#     return [x1, y1, x2, y2]


# def apply_shift_xyxy(bbox: list[float], shift_x: float, shift_y: float) -> list[float]:
#     x1, y1, x2, y2 = bbox
#     return [
#         x1 + shift_x,
#         y1 + shift_y,
#         x2 + shift_x,
#         y2 + shift_y,
#     ]


# def expand_para_block(block: dict[str, Any], page_idx: int | None) -> list[dict[str, Any]]:
#     out: list[dict[str, Any]] = []

#     raw_type = block.get("type")
#     if not isinstance(raw_type, str):
#         return out

#     raw_type = raw_type.strip().lower()

#     if raw_type != "table":
#         b = dict(block)
#         if "page_idx" not in b:
#             b["page_idx"] = page_idx
#         b["type"] = raw_type
#         out.append(b)
#         return out

#     inner_blocks = block.get("blocks", [])
#     if not isinstance(inner_blocks, list) or not inner_blocks:
#         b = dict(block)
#         if "page_idx" not in b:
#             b["page_idx"] = page_idx
#         b["type"] = raw_type
#         out.append(b)
#         return out

#     extracted_any = False

#     for inner in inner_blocks:
#         if not isinstance(inner, dict):
#             continue

#         inner_type = inner.get("type")
#         inner_bbox = inner.get("bbox")

#         if not isinstance(inner_type, str):
#             continue
#         if not is_valid_bbox(inner_bbox):
#             continue

#         child = dict(inner)
#         child["type"] = inner_type.strip().lower()
#         if "page_idx" not in child:
#             child["page_idx"] = page_idx
#         child["_parent_type"] = "table"

#         out.append(child)
#         extracted_any = True

#     if not extracted_any:
#         b = dict(block)
#         if "page_idx" not in b:
#             b["page_idx"] = page_idx
#         b["type"] = raw_type
#         out.append(b)

#     return out


# def extract_para_blocks(data: Any) -> list[dict[str, Any]]:
#     if not isinstance(data, dict):
#         return []

#     pdf_info = data.get("pdf_info")
#     if not isinstance(pdf_info, list):
#         return []

#     blocks: list[dict[str, Any]] = []

#     for page in pdf_info:
#         if not isinstance(page, dict):
#             continue

#         page_idx = page.get("page_idx")
#         para_blocks = page.get("para_blocks", [])
#         if not isinstance(para_blocks, list):
#             continue

#         for block in para_blocks:
#             if not isinstance(block, dict):
#                 continue

#             expanded = expand_para_block(block, page_idx)
#             blocks.extend(expanded)

#     return blocks


# def iter_primary_json_files() -> list[Path]:
#     files: list[Path] = []
#     for subdir in sorted(RAW_DIR.iterdir()):
#         if not subdir.is_dir():
#             continue
#         candidate = subdir / f"{subdir.name}.json"
#         if candidate.exists():
#             files.append(candidate)
#     return files


# def main() -> None:
#     if not GT_JSON.exists():
#         raise SystemExit(f"Missing GT json: {GT_JSON}")

#     image_info_map = load_gt_image_info()
#     json_files = iter_primary_json_files()

#     if not json_files:
#         raise SystemExit(f"No primary json found under {RAW_DIR}")

#     preds: list[dict[str, Any]] = []

#     total_blocks = 0
#     used_blocks = 0
#     skipped_unknown_type = 0
#     skipped_bad_bbox = 0
#     skipped_missing_image_id = 0

#     type_counter: dict[str, int] = {}

#     print(f"[INFO] primary json files = {len(json_files)}")
#     print(f"[INFO] apply shift: SHIFT_X={SHIFT_X}, SHIFT_Y={SHIFT_Y}")

#     for jf in json_files:
#         doc_id = jf.stem
#         image_info = image_info_map.get(doc_id)

#         if image_info is None:
#             print(f"[WARN] skip {doc_id}: not found in GT images")
#             skipped_missing_image_id += 1
#             continue

#         image_id = image_info["image_id"]
#         image_width = image_info["width"]
#         image_height = image_info["height"]

#         data = json.loads(jf.read_text(encoding="utf-8"))
#         blocks = extract_para_blocks(data)

#         if not blocks:
#             print(f"[WARN] skip {jf}: no valid blocks found")
#             continue

#         for block in blocks:
#             total_blocks += 1

#             raw_type = block.get("type")
#             if not isinstance(raw_type, str):
#                 skipped_unknown_type += 1
#                 continue

#             raw_type = raw_type.strip().lower()
#             type_counter[raw_type] = type_counter.get(raw_type, 0) + 1

#             target_name = MINERU_TYPE_TO_TARGET.get(raw_type)
#             if target_name is None:
#                 skipped_unknown_type += 1
#                 continue

#             bbox = block.get("bbox")
#             if not is_valid_bbox(bbox):
#                 skipped_bad_bbox += 1
#                 continue

#             bbox_xyxy = scale_bbox_if_needed(
#                 bbox=[float(v) for v in bbox],
#                 image_width=image_width,
#                 image_height=image_height,
#             )

#             bbox_xyxy = apply_shift_xyxy(
#                 bbox=bbox_xyxy,
#                 shift_x=SHIFT_X,
#                 shift_y=SHIFT_Y,
#             )

#             x, y, w, h = xyxy_to_xywh(bbox_xyxy)
#             if w <= 0 or h <= 0:
#                 skipped_bad_bbox += 1
#                 continue

#             preds.append(
#                 {
#                     "image_id": image_id,
#                     "category_id": CATEGORY_NAME_TO_ID[target_name],
#                     "bbox": [x, y, w, h],
#                     "score": 1.0,
#                 }
#             )
#             used_blocks += 1

#         print(f"[OK] {doc_id}: blocks={len(blocks)}")

#     OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
#     with OUT_JSON.open("w", encoding="utf-8") as f:
#         json.dump(preds, f, ensure_ascii=False, indent=2)

#     print(f"[OK] overwritten: {OUT_JSON}")
#     print(f"[INFO] total primary json files : {len(json_files)}")
#     print(f"[INFO] total blocks             : {total_blocks}")
#     print(f"[INFO] used blocks              : {used_blocks}")
#     print(f"[INFO] skipped unknown type     : {skipped_unknown_type}")
#     print(f"[INFO] skipped bad bbox         : {skipped_bad_bbox}")
#     print(f"[INFO] skipped missing imageid  : {skipped_missing_image_id}")
#     print(f"[INFO] total predictions        : {len(preds)}")

#     print("\n=== USED TYPES AFTER TABLE EXPANSION ===")
#     for k in sorted(type_counter):
#         print(f"{k:15s}: {type_counter[k]}")


# if __name__ == "__main__":
#     main()


# =================

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
OUTPUTS = ROOT / "outputs"
RAW_DIR = OUTPUTS / "mineru_raw"
GT_JSON = OUTPUTS / "gt" / "gt_5class_sample30.json"
OUT_JSON = OUTPUTS / "pred" / "pred_mineru_sample30.json"

# 可手動微調；先維持 0
SHIFT_X = 0
SHIFT_Y = 0

# 你目前是 5 類
CATEGORY_NAME_TO_ID = {
    "Picture": 0,
    "Section-header": 1,
    "Table": 2,
    "Text": 3,
    "Title": 4,
}


def sort_key_for_path_name(p: Path) -> tuple[int, Any]:
    """
    讓 1,2,3... 按數字排序；非純數字則退回字串排序。
    """
    try:
        return (0, int(p.name))
    except ValueError:
        return (1, p.name)


def find_primary_jsons(raw_dir: Path) -> list[Path]:
    """
    只找每個樣本資料夾底下，和資料夾同名的 json。
    例如：
      outputs/mineru_raw/1/1.json
      outputs/mineru_raw/2/2.json
    """
    json_paths: list[Path] = []

    if not raw_dir.exists():
        return []

    for sample_dir in sorted(raw_dir.iterdir(), key=sort_key_for_path_name):
        if not sample_dir.is_dir():
            continue

        target_json = sample_dir / f"{sample_dir.name}.json"
        if target_json.exists():
            json_paths.append(target_json)

    return json_paths


def load_gt_image_info() -> dict[str, dict[str, Any]]:
    """
    從 GT 讀出 image 對照資訊。
    以 image file_name 的 stem 當 key，例如:
      '1.png' -> key='1'
    """
    gt = json.loads(GT_JSON.read_text(encoding="utf-8"))

    out: dict[str, dict[str, Any]] = {}

    for img in gt.get("images", []):
        if not isinstance(img, dict):
            continue

        image_id = img.get("id")
        file_name = img.get("file_name")
        width = img.get("width")
        height = img.get("height")

        if not isinstance(image_id, int):
            continue
        if not isinstance(file_name, str):
            continue
        if not isinstance(width, int):
            continue
        if not isinstance(height, int):
            continue

        stem = Path(file_name).stem
        out[stem] = {
            "id": image_id,
            "file_name": file_name,
            "width": width,
            "height": height,
        }

    return out


def extract_blocks(data: Any) -> list[dict[str, Any]]:
    """
    目前新版 MinerU schema:
    [
      {
        "type": "text" | "table" | "page_number" | ...,
        "bbox": [x1, y1, x2, y2],
        "page_idx": 0,
        ...
      },
      ...
    ]
    """
    if not isinstance(data, list):
        return []

    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            out.append(item)
    return out


def normalize_bbox_xyxy(
    bbox: Any,
    width: int,
    height: int,
    shift_x: int = 0,
    shift_y: int = 0,
) -> list[float] | None:
    """
    將 MinerU bbox 視為 xyxy:
      [x1, y1, x2, y2]

    並裁切到影像範圍內。
    """
    if not isinstance(bbox, list) or len(bbox) != 4:
        return None

    try:
        x1 = float(bbox[0]) + shift_x
        y1 = float(bbox[1]) + shift_y
        x2 = float(bbox[2]) + shift_x
        y2 = float(bbox[3]) + shift_y
    except (TypeError, ValueError):
        return None

    # 修正顛倒
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    # clip 到影像範圍
    x1 = max(0.0, min(x1, float(width)))
    y1 = max(0.0, min(y1, float(height)))
    x2 = max(0.0, min(x2, float(width)))
    y2 = max(0.0, min(y2, float(height)))

    # clip 後再檢查
    if x2 <= x1 or y2 <= y1:
        return None

    return [x1, y1, x2, y2]


def xyxy_to_xywh(xyxy: list[float]) -> list[float]:
    x1, y1, x2, y2 = xyxy
    return [x1, y1, x2 - x1, y2 - y1]


def infer_target_category(block: dict[str, Any]) -> str | None:
    """
    將 MinerU block 映射到你的 5 類：
      Picture, Section-header, Table, Text, Title

    目前規則：
    - table -> Table
    - text + text_level >= 2 -> Title
    - text + text_level == 1 -> Section-header
    - text -> Text
    - page_number -> 忽略
    - 其他 -> 忽略
    """
    block_type = block.get("type")

    if block_type == "table":
        return "Table"

    if block_type == "text":
        text_level = block.get("text_level")

        if isinstance(text_level, int):
            if text_level >= 2:
                return "Title"
            if text_level == 1:
                return "Section-header"

        return "Text"

    if block_type == "page_number":
        return None

    return None


def build_prediction(
    image_id: int,
    category_id: int,
    bbox_xyxy: list[float],
    score: float = 1.0,
) -> dict[str, Any]:
    bbox_xywh = xyxy_to_xywh(bbox_xyxy)
    area = bbox_xywh[2] * bbox_xywh[3]

    return {
        "image_id": image_id,
        "category_id": category_id,
        "bbox": [round(v, 2) for v in bbox_xywh],
        "score": float(score),
        "area": round(area, 2),
    }


def main() -> None:
    gt_image_info = load_gt_image_info()
    json_files = find_primary_jsons(RAW_DIR)

    print(f"[INFO] primary json files = {len(json_files)}")
    print(f"[INFO] apply shift: SHIFT_X={SHIFT_X}, SHIFT_Y={SHIFT_Y}")

    predictions: list[dict[str, Any]] = []

    total_blocks = 0
    used_blocks = 0
    skipped_unknown_type = 0
    skipped_bad_bbox = 0
    skipped_missing_imageid = 0

    used_type_counter = Counter()
    raw_type_counter = Counter()
    mapped_category_counter = Counter()

    for json_path in json_files:
        sample_key = json_path.stem  # 1.json -> "1"
        image_meta = gt_image_info.get(sample_key)

        if image_meta is None:
            skipped_missing_imageid += 1
            print(f"[WARN] skip {json_path}: no matched image info in GT for key={sample_key}")
            continue

        image_id = image_meta["id"]
        width = image_meta["width"]
        height = image_meta["height"]

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] skip {json_path}: json load failed: {e}")
            continue

        blocks = extract_blocks(data)

        if not blocks:
            print(f"[WARN] skip {json_path}: no valid blocks found")
            continue

        file_used = 0

        for block in blocks:
            total_blocks += 1

            block_type = str(block.get("type", "<missing>"))
            raw_type_counter[block_type] += 1

            target_name = infer_target_category(block)
            if target_name is None:
                skipped_unknown_type += 1
                continue

            bbox_xyxy = normalize_bbox_xyxy(
                bbox=block.get("bbox"),
                width=width,
                height=height,
                shift_x=SHIFT_X,
                shift_y=SHIFT_Y,
            )
            if bbox_xyxy is None:
                skipped_bad_bbox += 1
                continue

            category_id = CATEGORY_NAME_TO_ID[target_name]
            pred = build_prediction(
                image_id=image_id,
                category_id=category_id,
                bbox_xyxy=bbox_xyxy,
                score=1.0,
            )
            predictions.append(pred)

            used_blocks += 1
            file_used += 1
            used_type_counter[block_type] += 1
            mapped_category_counter[target_name] += 1

        if file_used == 0:
            print(f"[WARN] skip {json_path}: blocks exist but none survived mapping/bbox checks")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] overwritten: {OUT_JSON}")
    print(f"[INFO] total primary json files : {len(json_files)}")
    print(f"[INFO] total blocks             : {total_blocks}")
    print(f"[INFO] used blocks              : {used_blocks}")
    print(f"[INFO] skipped unknown type     : {skipped_unknown_type}")
    print(f"[INFO] skipped bad bbox         : {skipped_bad_bbox}")
    print(f"[INFO] skipped missing imageid  : {skipped_missing_imageid}")
    print(f"[INFO] total predictions        : {len(predictions)}")

    print("\n=== RAW TYPES ===")
    for k, v in raw_type_counter.most_common():
        print(f"{k}: {v}")

    print("\n=== USED TYPES AFTER FILTER ===")
    for k, v in used_type_counter.most_common():
        print(f"{k}: {v}")

    print("\n=== MAPPED TARGET CATEGORIES ===")
    for k, v in mapped_category_counter.most_common():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()