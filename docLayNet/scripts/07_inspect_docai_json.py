from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

RAW_DIR = ROOT / "outputs" / "docai_raw"
OUT_DIR = ROOT / "outputs" / "docai_schema_summary"

PROCESSORS = ["form", "layout", "ocr"]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_len(v: Any) -> int:
    return len(v) if isinstance(v, list) else 0


def to_rows(counter: Counter, key_name: str) -> list[dict[str, Any]]:
    return [
        {key_name: k, "count": v}
        for k, v in sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))
    ]


# =========================================================
# OCR / FORM 共用 page 統計
# =========================================================
def collect_page_level_stats(data: Any) -> dict[str, int]:
    stats = Counter()

    if not isinstance(data, dict):
        return dict(stats)

    pages = data.get("pages", [])
    if not isinstance(pages, list):
        return dict(stats)

    stats["pages"] += len(pages)

    for page in pages:
        if not isinstance(page, dict):
            continue

        for key in [
            "blocks",
            "paragraphs",
            "lines",
            "tokens",
            "tables",
            "form_fields",
            "visual_elements",
        ]:
            stats[key] += safe_len(page.get(key))

    return dict(stats)


def collect_form_stats(data: Any) -> dict[str, Any]:
    stats = Counter()
    entity_type_counter = Counter()

    if not isinstance(data, dict):
        return {
            "totals": {},
            "entity_types": [],
        }

    # top-level entities
    entities = data.get("entities", [])
    if isinstance(entities, list):
        stats["entities"] += len(entities)

        for ent in entities:
            if not isinstance(ent, dict):
                continue
            stats["entity_properties"] += safe_len(ent.get("properties"))

            ent_type = ent.get("type_")
            if ent_type is not None:
                entity_type_counter[str(ent_type)] += 1

    # pages[] 內的各類元素總數
    page_stats = collect_page_level_stats(data)
    stats.update(page_stats)

    return {
        "totals": dict(stats),
        "entity_types": to_rows(entity_type_counter, "entity_type"),
    }


def collect_ocr_stats(data: Any) -> dict[str, Any]:
    stats = Counter()

    if not isinstance(data, dict):
        return {"totals": {}}

    page_stats = collect_page_level_stats(data)
    stats.update(page_stats)

    return {
        "totals": dict(stats),
    }


# =========================================================
# LAYOUT 專用 block tree 統計
# =========================================================
class LayoutAnalyzer:
    def __init__(self) -> None:
        self.totals = Counter()
        self.wrapper_types = Counter()
        self.text_block_types = Counter()
        self.depth_counter = Counter()

    def analyze(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return self._result()

        document_layout = data.get("document_layout")
        if not isinstance(document_layout, dict):
            return self._result()

        blocks = document_layout.get("blocks", [])
        if not isinstance(blocks, list):
            return self._result()

        self.totals["root_blocks"] += len(blocks)

        for block in blocks:
            self._walk_block(block, depth=1)

        return self._result()

    def _walk_block(self, block: Any, depth: int) -> None:
        if not isinstance(block, dict):
            return

        self.totals["all_blocks"] += 1
        self.depth_counter[depth] += 1

        wrapper_keys = [k for k in block.keys() if k.endswith("_block")]

        if not wrapper_keys:
            self.wrapper_types["<no_wrapper>"] += 1
            return

        for wk in wrapper_keys:
            self.wrapper_types[wk] += 1
            wrapper_obj = block.get(wk)

            if not isinstance(wrapper_obj, dict):
                continue

            # text_block.type_
            if wk == "text_block":
                t = wrapper_obj.get("type_")
                if t is not None:
                    self.text_block_types[str(t)] += 1

            # 一般內層 blocks
            inner_blocks = wrapper_obj.get("blocks")
            if isinstance(inner_blocks, list):
                self.totals["nested_blocks_refs"] += len(inner_blocks)
                for child in inner_blocks:
                    self._walk_block(child, depth + 1)

            # table/list 等更深層巢狀
            self._walk_nested_container(wrapper_obj, depth + 1)

    def _walk_nested_container(self, node: Any, depth: int) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                # 避免跟上面的 wrapper_obj["blocks"] 重複統計
                if k == "blocks":
                    continue

                if k == "cells" and isinstance(v, list):
                    self.totals["table_cells"] += len(v)

                if k == "header_rows" and isinstance(v, list):
                    self.totals["table_header_rows"] += len(v)

                if k == "body_rows" and isinstance(v, list):
                    self.totals["table_body_rows"] += len(v)

                if k == "list_entries" and isinstance(v, list):
                    self.totals["list_entries"] += len(v)

                if isinstance(v, list):
                    for item in v:
                        self._walk_nested_container(item, depth)
                elif isinstance(v, dict):
                    self._walk_nested_container(v, depth)

                # cells[].blocks 這種情況
                if k == "blocks" and isinstance(v, list):
                    for child in v:
                        self._walk_block(child, depth)

        elif isinstance(node, list):
            for item in node:
                self._walk_nested_container(item, depth)

    def _result(self) -> dict[str, Any]:
        return {
            "totals": dict(self.totals),
            "wrapper_types": to_rows(self.wrapper_types, "wrapper_type"),
            "text_block_types": to_rows(self.text_block_types, "text_block_type"),
            "depth_distribution": to_rows(self.depth_counter, "depth"),
        }


# =========================================================
# processor summary
# =========================================================
def summarize_processor(processor_name: str) -> None:
    processor_dir = RAW_DIR / processor_name
    if not processor_dir.exists():
        print(f"[WARN] processor dir not found: {processor_dir}")
        return

    json_paths = sorted(processor_dir.glob("*.json"))
    if not json_paths:
        print(f"[WARN] no json files found under: {processor_dir}")
        return

    files_scanned = []
    failed_files = []

    merged_totals = Counter()
    merged_entity_types = Counter()
    merged_wrapper_types = Counter()
    merged_text_block_types = Counter()
    merged_depth_distribution = Counter()

    for json_path in json_paths:
        try:
            data = load_json(json_path)
        except Exception as e:
            failed_files.append({
                "file": str(json_path),
                "error": str(e),
            })
            print(f"[WARN] failed to read {json_path}: {e}")
            continue

        files_scanned.append(str(json_path))

        if processor_name == "form":
            result = collect_form_stats(data)
            merged_totals.update(result["totals"])
            for row in result["entity_types"]:
                merged_entity_types[row["entity_type"]] += row["count"]

        elif processor_name == "ocr":
            result = collect_ocr_stats(data)
            merged_totals.update(result["totals"])

        elif processor_name == "layout":
            analyzer = LayoutAnalyzer()
            result = analyzer.analyze(data)

            merged_totals.update(result["totals"])
            for row in result["wrapper_types"]:
                merged_wrapper_types[row["wrapper_type"]] += row["count"]
            for row in result["text_block_types"]:
                merged_text_block_types[row["text_block_type"]] += row["count"]
            for row in result["depth_distribution"]:
                merged_depth_distribution[row["depth"]] += row["count"]

    summary: dict[str, Any] = {
        "processor": processor_name,
        "num_files_scanned": len(files_scanned),
        "num_files_failed": len(failed_files),
        "files_scanned": files_scanned,
        "failed_files": failed_files,
        "totals": to_rows(merged_totals, "item"),
    }

    if processor_name == "form":
        summary["entity_types"] = to_rows(merged_entity_types, "entity_type")

    if processor_name == "layout":
        summary["wrapper_types"] = to_rows(merged_wrapper_types, "wrapper_type")
        summary["text_block_types"] = to_rows(merged_text_block_types, "text_block_type")
        summary["depth_distribution"] = to_rows(merged_depth_distribution, "depth")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"{processor_name}_simple_summary.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # console output: 只印總表
    print("=" * 80)
    print(f"[OK] processor       : {processor_name}")
    print(f"[OK] scanned files   : {len(files_scanned)}")
    print(f"[OK] failed files    : {len(failed_files)}")
    print(f"[OK] summary saved to: {out_file}")

    print("\n[TOTALS]")
    for row in summary["totals"]:
        print(f"  {row['item']}: {row['count']}")

    if processor_name == "form":
        print("\n[ENTITY TYPES]")
        for row in summary["entity_types"]:
            print(f"  {row['entity_type']}: {row['count']}")

    if processor_name == "layout":
        print("\n[WRAPPER TYPES]")
        for row in summary["wrapper_types"]:
            print(f"  {row['wrapper_type']}: {row['count']}")

        print("\n[TEXT BLOCK TYPES]")
        for row in summary["text_block_types"]:
            print(f"  {row['text_block_type']}: {row['count']}")

        print("\n[DEPTH DISTRIBUTION]")
        for row in summary["depth_distribution"]:
            print(f"  depth={row['depth']}: {row['count']}")


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"DocAI raw dir not found: {RAW_DIR}")

    for processor in PROCESSORS:
        summarize_processor(processor)


if __name__ == "__main__":
    main()