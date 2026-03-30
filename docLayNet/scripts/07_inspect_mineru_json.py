# # from __future__ import annotations

# # import json
# # from collections import Counter
# # from pathlib import Path
# # from typing import Any


# # ROOT = Path(__file__).resolve().parents[1]
# # RAW_DIR = ROOT / "outputs" / "mineru_raw"


# # def find_primary_jsons(raw_dir: Path) -> list[Path]:
# #     """
# #     只找每個樣本資料夾底下，和資料夾同名的 json。
# #     例如：
# #       outputs/mineru_raw/1/1.json
# #       outputs/mineru_raw/2/2.json
# #     """
# #     json_paths: list[Path] = []

# #     for sample_dir in sorted(raw_dir.iterdir(), key=lambda p: p.name):
# #         if not sample_dir.is_dir():
# #             continue

# #         target_json = sample_dir / f"{sample_dir.name}.json"
# #         if target_json.exists():
# #             json_paths.append(target_json)

# #     return json_paths


# # def extract_para_blocks(data: Any) -> list[dict[str, Any]]:
# #     """
# #     第三份 MinerU JSON:
# #     {
# #       "pdf_info": [
# #         {
# #           "page_idx": 0,
# #           "page_size": [...],
# #           "para_blocks": [...]
# #         },
# #         ...
# #       ]
# #     }
# #     """
# #     if not isinstance(data, dict):
# #         return []

# #     pdf_info = data.get("pdf_info")
# #     if not isinstance(pdf_info, list):
# #         return []

# #     blocks: list[dict[str, Any]] = []

# #     for page in pdf_info:
# #         if not isinstance(page, dict):
# #             continue

# #         page_idx = page.get("page_idx")
# #         para_blocks = page.get("para_blocks", [])
# #         if not isinstance(para_blocks, list):
# #             continue

# #         for block in para_blocks:
# #             if not isinstance(block, dict):
# #                 continue

# #             b = dict(block)
# #             if "page_idx" not in b:
# #                 b["page_idx"] = page_idx
# #             blocks.append(b)

# #     return blocks


# # def extract_text_from_block(block: dict[str, Any]) -> str:
# #     parts: list[str] = []

# #     for line in block.get("lines", []):
# #         if not isinstance(line, dict):
# #             continue
# #         for span in line.get("spans", []):
# #             if not isinstance(span, dict):
# #                 continue
# #             content = span.get("content")
# #             if isinstance(content, str):
# #                 parts.append(content)

# #     return "".join(parts).strip()


# # def extract_image_paths_from_block(block: dict[str, Any]) -> list[str]:
# #     paths: list[str] = []

# #     for sub_block in block.get("blocks", []):
# #         if not isinstance(sub_block, dict):
# #             continue
# #         for line in sub_block.get("lines", []):
# #             if not isinstance(line, dict):
# #                 continue
# #             for span in line.get("spans", []):
# #                 if not isinstance(span, dict):
# #                     continue
# #                 image_path = span.get("image_path")
# #                 if isinstance(image_path, str):
# #                     paths.append(image_path)

# #     return paths


# # def preview_block(block: dict[str, Any]) -> dict[str, Any]:
# #     out: dict[str, Any] = {
# #         "type": block.get("type"),
# #         "bbox": block.get("bbox"),
# #         "page_idx": block.get("page_idx"),
# #         "keys": list(block.keys()),
# #     }

# #     text = extract_text_from_block(block)
# #     if text:
# #         out["text_preview"] = text[:120]

# #     image_paths = extract_image_paths_from_block(block)
# #     if image_paths:
# #         out["image_paths"] = image_paths[:3]

# #     return out


# # def inspect_one_json(json_path: Path) -> dict[str, Any]:
# #     data = json.loads(json_path.read_text(encoding="utf-8"))

# #     pdf_info = data.get("pdf_info", [])
# #     num_pages = len(pdf_info) if isinstance(pdf_info, list) else 0

# #     blocks = extract_para_blocks(data)
# #     type_counter = Counter()

# #     for block in blocks:
# #         block_type = block.get("type", "<missing>")
# #         type_counter[str(block_type)] += 1

# #     previews = [preview_block(b) for b in blocks[:5]]

# #     return {
# #         "json_path": str(json_path),
# #         "num_pages": num_pages,
# #         "num_blocks": len(blocks),
# #         "type_counter": dict(type_counter),
# #         "previews": previews,
# #     }


# # def main() -> None:
# #     json_files = find_primary_jsons(RAW_DIR)

# #     if not json_files:
# #         print(f"[WARN] no primary json found under: {RAW_DIR}")
# #         return

# #     print("=" * 100)
# #     print("[TARGET JSON FILES]")
# #     for p in json_files:
# #         print(p)

# #     total_files = 0
# #     total_pages = 0
# #     total_blocks = 0
# #     global_type_counter = Counter()

# #     all_results: list[dict[str, Any]] = []

# #     for json_path in json_files:
# #         print("\n" + "=" * 100)
# #         print(f"[FILE] {json_path}")

# #         result = inspect_one_json(json_path)
# #         all_results.append(result)

# #         total_files += 1
# #         total_pages += result["num_pages"]
# #         total_blocks += result["num_blocks"]
# #         global_type_counter.update(result["type_counter"])

# #         print(f"pages      : {result['num_pages']}")
# #         print(f"blocks     : {result['num_blocks']}")
# #         print(f"type_count : {result['type_counter']}")

# #         print("[PREVIEW BLOCKS]")
# #         for i, item in enumerate(result["previews"], start=1):
# #             print(f"  ({i}) {json.dumps(item, ensure_ascii=False)}")

# #     print("\n" + "=" * 100)
# #     print("[SUMMARY]")
# #     print(f"total_files  : {total_files}")
# #     print(f"total_pages  : {total_pages}")
# #     print(f"total_blocks : {total_blocks}")
# #     print(f"global_types : {dict(global_type_counter)}")


# # if __name__ == "__main__":
# #     main()

# #=========================================================

# from __future__ import annotations

# import json
# from collections import Counter
# from pathlib import Path
# from typing import Any


# ROOT = Path(__file__).resolve().parents[1]
# RAW_DIR = ROOT / "outputs" / "mineru_raw"


# def sort_key_for_path_name(p: Path) -> tuple[int, Any]:
#     """
#     讓資料夾名稱像 1,2,3 可以按數字排序；
#     若不是純數字，就退回字串排序。
#     """
#     try:
#         return (0, int(p.name))
#     except ValueError:
#         return (1, p.name)


# def find_primary_jsons(raw_dir: Path) -> list[Path]:
#     """
#     只找每個樣本資料夾底下，和資料夾同名的 json。
#     例如：
#       outputs/mineru_raw/1/1.json
#       outputs/mineru_raw/2/2.json
#     """
#     json_paths: list[Path] = []

#     if not raw_dir.exists():
#         return []

#     for sample_dir in sorted(raw_dir.iterdir(), key=sort_key_for_path_name):
#         if not sample_dir.is_dir():
#             continue

#         target_json = sample_dir / f"{sample_dir.name}.json"
#         if target_json.exists():
#             json_paths.append(target_json)

#     return json_paths


# def extract_blocks(data: Any) -> list[dict[str, Any]]:
#     """
#     新版 MinerU JSON 結構：
#     [
#       {
#         "type": "text" | "table" | "page_number" | ...,
#         "bbox": [x1, y1, x2, y2],
#         "page_idx": 0,
#         ...
#       },
#       ...
#     ]
#     """
#     if not isinstance(data, list):
#         return []

#     out: list[dict[str, Any]] = []
#     for item in data:
#         if isinstance(item, dict):
#             out.append(item)
#     return out


# def extract_text_from_block(block: dict[str, Any]) -> str:
#     """
#     依照不同 block 類型抓代表內容。
#     """
#     block_type = block.get("type")

#     if block_type == "text":
#         text = block.get("text")
#         return text.strip() if isinstance(text, str) else ""

#     if block_type == "table":
#         table_body = block.get("table_body")
#         return table_body.strip() if isinstance(table_body, str) else ""

#     # 其他未知類型，盡量 fallback 抓 text
#     text = block.get("text")
#     if isinstance(text, str):
#         return text.strip()

#     return ""


# def extract_image_paths_from_block(block: dict[str, Any]) -> list[str]:
#     """
#     新 schema 下，table 直接有 img_path。
#     """
#     paths: list[str] = []

#     img_path = block.get("img_path")
#     if isinstance(img_path, str) and img_path.strip():
#         paths.append(img_path.strip())

#     return paths


# def preview_block(block: dict[str, Any]) -> dict[str, Any]:
#     out: dict[str, Any] = {
#         "type": block.get("type"),
#         "bbox": block.get("bbox"),
#         "page_idx": block.get("page_idx"),
#         "keys": list(block.keys()),
#     }

#     if "text_level" in block:
#         out["text_level"] = block.get("text_level")

#     text = extract_text_from_block(block)
#     if text:
#         out["content_preview"] = text[:180]

#     image_paths = extract_image_paths_from_block(block)
#     if image_paths:
#         out["image_paths"] = image_paths[:3]

#     if block.get("type") == "table":
#         table_caption = block.get("table_caption")
#         table_footnote = block.get("table_footnote")
#         if isinstance(table_caption, list):
#             out["table_caption_count"] = len(table_caption)
#         if isinstance(table_footnote, list):
#             out["table_footnote_count"] = len(table_footnote)

#     return out


# def inspect_one_json(json_path: Path) -> dict[str, Any]:
#     data = json.loads(json_path.read_text(encoding="utf-8"))

#     blocks = extract_blocks(data)

#     type_counter = Counter()
#     page_counter = Counter()

#     for block in blocks:
#         block_type = str(block.get("type", "<missing>"))
#         type_counter[block_type] += 1

#         page_idx = block.get("page_idx")
#         if isinstance(page_idx, int):
#             page_counter[page_idx] += 1

#     num_pages = len(page_counter)
#     previews = [preview_block(b) for b in blocks[:8]]

#     table_blocks = [b for b in blocks if b.get("type") == "table"]
#     table_previews = [preview_block(b) for b in table_blocks[:3]]

#     return {
#         "json_path": str(json_path),
#         "root_type": type(data).__name__,
#         "num_pages": num_pages,
#         "num_blocks": len(blocks),
#         "type_counter": dict(type_counter),
#         "page_counter": dict(page_counter),
#         "previews": previews,
#         "table_previews": table_previews,
#     }


# def main() -> None:
#     json_files = find_primary_jsons(RAW_DIR)

#     if not json_files:
#         print(f"[WARN] no primary json found under: {RAW_DIR}")
#         return

#     print("=" * 100)
#     print("[TARGET JSON FILES]")
#     for p in json_files:
#         print(p)

#     total_files = 0
#     total_pages = 0
#     total_blocks = 0
#     global_type_counter = Counter()

#     for json_path in json_files:
#         print("\n" + "=" * 100)
#         print(f"[FILE] {json_path}")

#         result = inspect_one_json(json_path)

#         total_files += 1
#         total_pages += result["num_pages"]
#         total_blocks += result["num_blocks"]
#         global_type_counter.update(result["type_counter"])

#         print(f"root_type   : {result['root_type']}")
#         print(f"pages       : {result['num_pages']}")
#         print(f"blocks      : {result['num_blocks']}")
#         print(f"type_count  : {result['type_counter']}")
#         print(f"page_count  : {result['page_counter']}")

#         print("[PREVIEW BLOCKS]")
#         for i, item in enumerate(result["previews"], start=1):
#             print(f"  ({i}) {json.dumps(item, ensure_ascii=False)}")

#         if result["table_previews"]:
#             print("[TABLE PREVIEWS]")
#             for i, item in enumerate(result["table_previews"], start=1):
#                 print(f"  ({i}) {json.dumps(item, ensure_ascii=False)}")

#     print("\n" + "=" * 100)
#     print("[SUMMARY]")
#     print(f"total_files   : {total_files}")
#     print(f"total_pages   : {total_pages}")
#     print(f"total_blocks  : {total_blocks}")
#     print(f"global_types  : {dict(global_type_counter)}")


# if __name__ == "__main__":
#     main()

# =================================================
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "outputs" / "mineru_raw"


def sort_key_for_path_name(p: Path) -> tuple[int, Any]:
    """
    讓資料夾名稱像 1,2,3 可以按數字排序；
    若不是純數字，就退回字串排序。
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


def extract_blocks(data: Any) -> list[dict[str, Any]]:
    """
    新版 MinerU JSON 結構：
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


def extract_text_from_block(block: dict[str, Any]) -> str:
    """
    依照不同 block 類型抓代表內容。
    """
    block_type = block.get("type")

    if block_type == "text":
        text = block.get("text")
        return text.strip() if isinstance(text, str) else ""

    if block_type == "table":
        table_body = block.get("table_body")
        return table_body.strip() if isinstance(table_body, str) else ""

    # 其他未知類型，盡量 fallback 抓 text
    text = block.get("text")
    if isinstance(text, str):
        return text.strip()

    return ""


def extract_image_paths_from_block(block: dict[str, Any]) -> list[str]:
    """
    新 schema 下，table 直接有 img_path。
    """
    paths: list[str] = []

    img_path = block.get("img_path")
    if isinstance(img_path, str) and img_path.strip():
        paths.append(img_path.strip())

    return paths


def preview_block(block: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": block.get("type"),
        "bbox": block.get("bbox"),
        "page_idx": block.get("page_idx"),
        "keys": list(block.keys()),
    }

    if "text_level" in block:
        out["text_level"] = block.get("text_level")

    text = extract_text_from_block(block)
    if text:
        out["content_preview"] = text[:180]

    image_paths = extract_image_paths_from_block(block)
    if image_paths:
        out["image_paths"] = image_paths[:3]

    if block.get("type") == "table":
        table_caption = block.get("table_caption")
        table_footnote = block.get("table_footnote")
        if isinstance(table_caption, list):
            out["table_caption_count"] = len(table_caption)
        if isinstance(table_footnote, list):
            out["table_footnote_count"] = len(table_footnote)

    return out


def inspect_one_json(json_path: Path) -> dict[str, Any]:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    blocks = extract_blocks(data)

    type_counter = Counter()
    page_counter = Counter()

    for block in blocks:
        block_type = str(block.get("type", "<missing>"))
        type_counter[block_type] += 1

        page_idx = block.get("page_idx")
        if isinstance(page_idx, int):
            page_counter[page_idx] += 1

    num_pages = len(page_counter)
    previews = [preview_block(b) for b in blocks[:8]]

    table_blocks = [b for b in blocks if b.get("type") == "table"]
    table_previews = [preview_block(b) for b in table_blocks[:3]]

    return {
        "json_path": str(json_path),
        "root_type": type(data).__name__,
        "num_pages": num_pages,
        "num_blocks": len(blocks),
        "type_counter": dict(type_counter),
        "page_counter": dict(page_counter),
        "previews": previews,
        "table_previews": table_previews,
    }


def main() -> None:
    json_files = find_primary_jsons(RAW_DIR)

    if not json_files:
        print(f"[WARN] no primary json found under: {RAW_DIR}")
        return

    print("=" * 100)
    print("[TARGET JSON FILES]")
    for p in json_files:
        print(p)

    total_files = 0
    total_pages = 0
    total_blocks = 0
    global_type_counter = Counter()

    for json_path in json_files:
        print("\n" + "=" * 100)
        print(f"[FILE] {json_path}")

        result = inspect_one_json(json_path)

        total_files += 1
        total_pages += result["num_pages"]
        total_blocks += result["num_blocks"]
        global_type_counter.update(result["type_counter"])

        print(f"root_type   : {result['root_type']}")
        print(f"pages       : {result['num_pages']}")
        print(f"blocks      : {result['num_blocks']}")
        print(f"type_count  : {result['type_counter']}")
        print(f"page_count  : {result['page_counter']}")

        print("[PREVIEW BLOCKS]")
        for i, item in enumerate(result["previews"], start=1):
            print(f"  ({i}) {json.dumps(item, ensure_ascii=False)}")

        if result["table_previews"]:
            print("[TABLE PREVIEWS]")
            for i, item in enumerate(result["table_previews"], start=1):
                print(f"  ({i}) {json.dumps(item, ensure_ascii=False)}")

    print("\n" + "=" * 100)
    print("[SUMMARY]")
    print(f"total_files   : {total_files}")
    print(f"total_pages   : {total_pages}")
    print(f"total_blocks  : {total_blocks}")
    print(f"global_types  : {dict(global_type_counter)}")


if __name__ == "__main__":
    main()