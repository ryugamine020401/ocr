from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docai_idps.stage1_ingest.pipeline import run_stage1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 1 PDF ingestion.")
    parser.add_argument("--input", required=True, type=Path, help="Path to the input PDF")
    parser.add_argument("--doc-id", type=str, default=None, help="Optional document ID")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data" / "outputs" / "stage1_ingest",
        help="Root directory for Stage 1 outputs",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rasterization DPI for page images",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output directory if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    document = run_stage1(
        input_path=args.input,
        project_root=PROJECT_ROOT,
        output_root=args.output_root,
        doc_id=args.doc_id,
        dpi=args.dpi,
        overwrite=args.overwrite,
    )

    print(f"[OK] doc_id      : {document.doc_id}")
    print(f"[OK] source_file : {document.source_file}")
    print(f"[OK] num_pages   : {document.num_pages}")
    print(
        "[OK] output_dir  : "
        f"{(args.output_root / document.doc_id).resolve()}"
    )


if __name__ == "__main__":
    main()
