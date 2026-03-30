from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "docling_raw"
OUT_FILE = ROOT / "outputs" / "docling_schema_summary.json"


TARGET_SECTIONS = [
    "texts",
    "tables",
    "pictures",
    "groups",
    "key_value_items",
    "form_items",
    "pages",
    "body",
    "items",
]


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
    section_item_key_counter: dict[str, Counter],
    label_counter: Counter,
    coord_origin_counter: Counter,
    prov_key_counter: Counter,
    bbox_key_counter: Counter,
    pages_type_counter: Counter,
    examples: dict,
) -> None:
    # top-level keys
    for key in data.keys():
        top_level_counter[key] += 1

    # target section presence
    for sec in TARGET_SECTIONS:
        if sec in data:
            section_presence_counter[sec] += 1

    # pages type
    pages = data.get("pages")
    if pages is not None:
        pages_type_counter[type(pages).__name__] += 1
        if "pages_example" not in examples:
            examples["pages_example"] = {
                "file_id": file_id,
                "type": type(pages).__name__,
                "preview_keys": list(pages.keys()) if isinstance(pages, dict) else None,
            }

    # scan common sections
    for sec in TARGET_SECTIONS:
        value = data.get(sec)
        if value is None:
            continue

        if isinstance(value, list):
            for item in value:
                sig = normalize_key_signature(item)
                section_item_key_counter[sec][sig] += 1

                if isinstance(item, dict):
                    if "label" in item:
                        label = item.get("label")
                        if label is not None:
                            label_counter[str(label)] += 1

                    prov_list = item.get("prov", [])
                    if isinstance(prov_list, list):
                        for prov in prov_list:
                            if not isinstance(prov, dict):
                                continue
                            prov_key_counter[normalize_key_signature(prov)] += 1

                            bbox = prov.get("bbox")
                            if isinstance(bbox, dict):
                                bbox_key_counter[normalize_key_signature(bbox)] += 1
                                origin = bbox.get("coord_origin")
                                if origin is not None:
                                    coord_origin_counter[str(origin)] += 1

                if f"{sec}_example" not in examples and isinstance(item, dict):
                    examples[f"{sec}_example"] = {
                        "file_id": file_id,
                        "keys": list(item.keys()),
                        "label": item.get("label"),
                    }

        elif isinstance(value, dict):
            sig = normalize_key_signature(value)
            section_item_key_counter[sec][sig] += 1
            if f"{sec}_example" not in examples:
                examples[f"{sec}_example"] = {
                    "file_id": file_id,
                    "keys": list(value.keys()),
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
        raise SystemExit(f"Docling raw dir not found: {RAW_DIR}")

    json_paths = sorted(RAW_DIR.glob("*/*.json"))
    if not json_paths:
        raise SystemExit(f"No json files found under: {RAW_DIR}")

    top_level_counter = Counter()
    section_presence_counter = Counter()
    section_item_key_counter = defaultdict(Counter)
    label_counter = Counter()
    coord_origin_counter = Counter()
    prov_key_counter = Counter()
    bbox_key_counter = Counter()
    pages_type_counter = Counter()
    examples = {}

    scanned_files = []

    for json_path in json_paths:
        file_id = json_path.stem
        try:
            data = load_json(json_path)
        except Exception as e:
            print(f"[WARN] failed to read {json_path}: {e}")
            continue

        scanned_files.append(str(json_path))
        scan_doc(
            data=data,
            file_id=file_id,
            top_level_counter=top_level_counter,
            section_presence_counter=section_presence_counter,
            section_item_key_counter=section_item_key_counter,
            label_counter=label_counter,
            coord_origin_counter=coord_origin_counter,
            prov_key_counter=prov_key_counter,
            bbox_key_counter=bbox_key_counter,
            pages_type_counter=pages_type_counter,
            examples=examples,
        )

    summary = {
        "num_files_scanned": len(scanned_files),
        "files_scanned": scanned_files,
        "top_level_keys": counter_to_sorted_list(top_level_counter, "key", "count"),
        "section_presence": counter_to_sorted_list(section_presence_counter, "section", "count"),
        "pages_types": counter_to_sorted_list(pages_type_counter, "type", "count"),
        "labels": counter_to_sorted_list(label_counter, "label", "count"),
        "coord_origins": counter_to_sorted_list(coord_origin_counter, "coord_origin", "count"),
        "prov_key_formats": tuple_counter_to_sorted_list(prov_key_counter),
        "bbox_key_formats": tuple_counter_to_sorted_list(bbox_key_counter),
        "section_item_formats": {
            sec: tuple_counter_to_sorted_list(counter)
            for sec, counter in sorted(section_item_key_counter.items())
        },
        "examples": examples,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"[OK] scanned files: {len(scanned_files)}")
    print(f"[OK] summary saved to: {OUT_FILE}")

    print("\n[TOP LEVEL KEYS]")
    for row in summary["top_level_keys"]:
        print(f"  {row['key']}: {row['count']}")

    print("\n[SECTION PRESENCE]")
    for row in summary["section_presence"]:
        print(f"  {row['section']}: {row['count']}")

    print("\n[LABELS]")
    for row in summary["labels"]:
        print(f"  {row['label']}: {row['count']}")

    print("\n[COORD ORIGINS]")
    for row in summary["coord_origins"]:
        print(f"  {row['coord_origin']}: {row['count']}")

    print("\n[SECTION ITEM FORMATS]")
    for sec, rows in summary["section_item_formats"].items():
        print(f"\n  - {sec}")
        for row in rows:
            print(f"      count={row['count']}, keys={row['keys']}")


if __name__ == "__main__":
    main()