from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "docling_raw"

# 先看哪一張
SAMPLE_ID = "1"


def print_keys(title: str, obj, depth: int = 0) -> None:
    indent = "  " * depth
    if isinstance(obj, dict):
        print(f"{indent}{title}: dict, keys={list(obj.keys())}")
    elif isinstance(obj, list):
        print(f"{indent}{title}: list, len={len(obj)}")
        if obj:
            first = obj[0]
            if isinstance(first, dict):
                print(f"{indent}  first item keys={list(first.keys())}")
            else:
                print(f"{indent}  first item type={type(first).__name__}, value={first}")
    else:
        print(f"{indent}{title}: {type(obj).__name__} = {obj}")


def main() -> None:
    json_path = RAW_DIR / SAMPLE_ID / f"{SAMPLE_ID}.json"

    if not json_path.exists():
        raise SystemExit(f"Docling json not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    print("=" * 80)
    print("[TOP LEVEL]")
    print_keys("root", data)

    for key, value in data.items():
        print_keys(key, value, depth=1)

    print("\n" + "=" * 80)
    print("[COMMON CANDIDATE FIELDS]")
    for key in ["pages", "items", "body", "texts", "tables", "pictures", "groups"]:
        if key in data:
            print_keys(key, data[key], depth=1)

    print("\n" + "=" * 80)
    print("[FIRST PAGE DETAIL]")
    pages = data.get("pages")
    if isinstance(pages, list) and pages:
        page0 = pages[0]
        print_keys("pages[0]", page0)
        if isinstance(page0, dict):
            for k, v in page0.items():
                print_keys(f"pages[0]['{k}']", v, depth=1)

    print("\n" + "=" * 80)
    print("[PREVIEW SNIPPETS]")

    # 印幾個常見候選內容
    if isinstance(pages, list) and pages:
        page0 = pages[0]
        if isinstance(page0, dict):
            for k in page0.keys():
                v = page0[k]
                if isinstance(v, list) and v:
                    print(f"\n--- pages[0]['{k}'] first item preview ---")
                    pprint(v[0], width=120)

    for key in ["items", "body", "texts", "tables", "pictures", "groups"]:
        v = data.get(key)
        if isinstance(v, list) and v:
            print(f"\n--- root['{key}'] first item preview ---")
            pprint(v[0], width=120)


if __name__ == "__main__":
    main()