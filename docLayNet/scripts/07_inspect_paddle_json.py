from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "paddle_raw"
OUT_FILE = ROOT / "outputs" / "paddle_schema_summary.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_key_signature(obj) -> tuple[str, ...]:
    if isinstance(obj, dict):
        return tuple(sorted(obj.keys()))
    return (f"<{type(obj).__name__}>",)


def scan_doc(
    data: dict,
    file_id: str,
    top_level_counter: Counter,
    section_presence_counter: Counter,
    block_key_counter: Counter,
    block_type_counter: Counter,
    bbox_len_counter: Counter,
    bbox_value_type_counter: Counter,
    image_key_counter: Counter,
    examples: dict,
) -> None:
    # top-level keys
    for key in data.keys():
        top_level_counter[key] += 1

    # section presence
    for sec in ["blocks", "image"]:
        if sec in data:
            section_presence_counter[sec] += 1

    # image section
    image = data.get("image")
    if isinstance(image, dict):
        image_key_counter[normalize_key_signature(image)] += 1
        if "image_example" not in examples:
            examples["image_example"] = {
                "file_id": file_id,
                "keys": list(image.keys()),
                "path": image.get("path"),
            }

    # blocks section
    blocks = data.get("blocks")
    if isinstance(blocks, list):
        if "blocks_example_count" not in examples:
            examples["blocks_example_count"] = {
                "file_id": file_id,
                "num_blocks": len(blocks),
            }

        for block in blocks:
            sig = normalize_key_signature(block)
            block_key_counter[sig] += 1

            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type is not None:
                    block_type_counter[str(block_type)] += 1

                bbox = block.get("bbox")
                if isinstance(bbox, list):
                    bbox_len_counter[len(bbox)] += 1
                    for v in bbox:
                        bbox_value_type_counter[type(v).__name__] += 1

                if "block_example" not in examples:
                    examples["block_example"] = {
                        "file_id": file_id,
                        "keys": list(block.keys()),
                        "type": block.get("type"),
                        "bbox": block.get("bbox"),
                        "text_preview": str(block.get("text", ""))[:80],
                    }


def counter_to_sorted_list(counter: Counter, key_name: str, value_name: str) -> list[dict]:
    return [
        {key_name: k, value_name: v}
        for k, v in sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
    ]


def tuple_counter_to_sorted_list(counter: Counter) -> list[dict]:
    out = []
    for keys, count in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
        out.append({
            "keys": list(keys),
            "count": count,
        })
    return out


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"Paddle raw dir not found: {RAW_DIR}")

    json_paths = sorted(RAW_DIR.glob("*/*.json"))
    if not json_paths:
        raise SystemExit(f"No json files found under: {RAW_DIR}")

    top_level_counter = Counter()
    section_presence_counter = Counter()
    block_key_counter = Counter()
    block_type_counter = Counter()
    bbox_len_counter = Counter()
    bbox_value_type_counter = Counter()
    image_key_counter = Counter()
    examples = {}

    scanned_files = []
    failed_files = []

    for json_path in json_paths:
        file_id = json_path.stem
        try:
            data = load_json(json_path)
        except Exception as e:
            print(f"[WARN] failed to read {json_path}: {e}")
            failed_files.append(str(json_path))
            continue

        scanned_files.append(str(json_path))
        scan_doc(
            data=data,
            file_id=file_id,
            top_level_counter=top_level_counter,
            section_presence_counter=section_presence_counter,
            block_key_counter=block_key_counter,
            block_type_counter=block_type_counter,
            bbox_len_counter=bbox_len_counter,
            bbox_value_type_counter=bbox_value_type_counter,
            image_key_counter=image_key_counter,
            examples=examples,
        )

    summary = {
        "num_files_scanned": len(scanned_files),
        "num_failed_files": len(failed_files),
        "files_scanned": scanned_files,
        "failed_files": failed_files,
        "top_level_keys": counter_to_sorted_list(top_level_counter, "key", "count"),
        "section_presence": counter_to_sorted_list(section_presence_counter, "section", "count"),
        "block_key_formats": tuple_counter_to_sorted_list(block_key_counter),
        "block_types": counter_to_sorted_list(block_type_counter, "type", "count"),
        "bbox_lengths": counter_to_sorted_list(bbox_len_counter, "length", "count"),
        "bbox_value_types": counter_to_sorted_list(bbox_value_type_counter, "type", "count"),
        "image_key_formats": tuple_counter_to_sorted_list(image_key_counter),
        "examples": examples,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"[OK] scanned files: {len(scanned_files)}")
    print(f"[OK] failed files : {len(failed_files)}")
    print(f"[OK] summary saved to: {OUT_FILE}")

    print("\n[TOP LEVEL KEYS]")
    for row in summary["top_level_keys"]:
        print(f"  {row['key']}: {row['count']}")

    print("\n[SECTION PRESENCE]")
    for row in summary["section_presence"]:
        print(f"  {row['section']}: {row['count']}")

    print("\n[BLOCK TYPES]")
    for row in summary["block_types"]:
        print(f"  {row['type']}: {row['count']}")

    print("\n[BBOX LENGTHS]")
    for row in summary["bbox_lengths"]:
        print(f"  {row['length']}: {row['count']}")

    print("\n[BBOX VALUE TYPES]")
    for row in summary["bbox_value_types"]:
        print(f"  {row['type']}: {row['count']}")

    print("\n[BLOCK KEY FORMATS]")
    for row in summary["block_key_formats"]:
        print(f"  count={row['count']}, keys={row['keys']}")

    print("\n[IMAGE KEY FORMATS]")
    for row in summary["image_key_formats"]:
        print(f"  count={row['count']}, keys={row['keys']}")


if __name__ == "__main__":
    main()