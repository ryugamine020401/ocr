from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
RAW_DIR = ROOT / "outputs" / "mineru_raw"


def unwrap_blocks(data: Any) -> list[dict[str, Any]]:
    """
    MinerU 可能是：
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


def is_valid_bbox(bbox: Any) -> bool:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    return all(isinstance(v, (int, float)) for v in bbox)


def detect_bbox_mode(blocks: list[dict[str, Any]]) -> str:
    """
    粗略判斷這份 json 的 bbox 是：
    - normalized (0~1)
    - pixel
    - unknown
    """
    max_coord = 0.0
    found = False

    for block in blocks:
        bbox = block.get("bbox")
        if not is_valid_bbox(bbox):
            continue
        found = True
        max_coord = max(max_coord, *[float(v) for v in bbox])

    if not found:
        return "unknown"
    if max_coord <= 1.5:
        return "normalized"
    return "pixel"


def preview_block(block: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    for k, v in block.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            text = v
            if isinstance(text, str) and len(text) > 150:
                text = text[:150] + "..."
            out[k] = text
        elif isinstance(v, list):
            out[k] = f"<list len={len(v)}>"
        elif isinstance(v, dict):
            out[k] = f"<dict keys={list(v.keys())[:10]}>"
        else:
            out[k] = f"<{type(v).__name__}>"

    return out


def main() -> None:
    json_files = sorted(RAW_DIR.rglob("*.json"))
    json_files = [p for p in json_files if p.name != "_meta.json"]

    if not json_files:
        raise SystemExit(f"No json found under {RAW_DIR}")

    total_blocks = 0
    root_type_counter = Counter()
    outer_type_counter = Counter()
    bbox_mode_counter = Counter()
    bbox_shape_counter = Counter()
    per_file_type_counter: dict[str, Counter] = {}
    sample_blocks_by_type: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    print(f"[INFO] total json files found: {len(json_files)}")

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] failed to read {jf}: {e}")
            continue

        root_type_counter[type(data).__name__] += 1

        blocks = unwrap_blocks(data)
        bbox_mode = detect_bbox_mode(blocks)
        bbox_mode_counter[bbox_mode] += 1

        file_counter = Counter()

        for block in blocks:
            if not isinstance(block, dict):
                continue

            total_blocks += 1

            raw_type = block.get("type")
            raw_type = raw_type.strip().lower() if isinstance(raw_type, str) else "<missing>"
            outer_type_counter[raw_type] += 1
            file_counter[raw_type] += 1

            bbox = block.get("bbox")
            if isinstance(bbox, list):
                bbox_shape_counter[f"list_len_{len(bbox)}"] += 1
            elif bbox is None:
                bbox_shape_counter["missing"] += 1
            else:
                bbox_shape_counter[type(bbox).__name__] += 1

            if len(sample_blocks_by_type[raw_type]) < 3:
                sample_blocks_by_type[raw_type].append((str(jf), preview_block(block)))

        per_file_type_counter[str(jf)] = file_counter

    print("\n=== GLOBAL SUMMARY ===")
    print(f"total_json_files = {len(json_files)}")
    print(f"total_blocks     = {total_blocks}")

    print("\n=== ROOT TYPE COUNTS ===")
    for k, v in root_type_counter.most_common():
        print(f"{k:15s}: {v}")

    print("\n=== BBOX MODE COUNTS ===")
    for k, v in bbox_mode_counter.most_common():
        print(f"{k:15s}: {v}")

    print("\n=== BBOX SHAPE COUNTS ===")
    for k, v in bbox_shape_counter.most_common():
        print(f"{k:15s}: {v}")

    print("\n=== OUTER BLOCK TYPE COUNTS ===")
    for k, v in outer_type_counter.most_common():
        print(f"{k:15s}: {v}")

    print("\n=== PER FILE TYPE COUNTS ===")
    for path, counter in per_file_type_counter.items():
        short_name = Path(path).name
        total_in_file = sum(counter.values())
        detail = ", ".join(f"{k}={v}" for k, v in counter.most_common())
        print(f"{short_name:20s} total={total_in_file:3d} | {detail}")

    print("\n=== SAMPLE BLOCKS BY TYPE ===")
    for block_type, items in sample_blocks_by_type.items():
        print(f"\n--- type = {block_type} ---")
        for path, preview in items:
            print(f"[FILE] {path}")
            print(json.dumps(preview, ensure_ascii=False, indent=2))

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()