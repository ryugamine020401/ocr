from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docai_idps.stage1_ingest.pipeline import run_stage1, slugify_doc_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 1 ingestion for all PDFs in a directory.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "inputs" / "raw" / "pdf",
        help="Directory containing input PDFs",
    )
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
        help="Overwrite existing output files for matching doc IDs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    pdf_paths = sorted(input_dir.glob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found in: {input_dir}")

    print(f"[INFO] input_dir   : {input_dir}")
    print(f"[INFO] num_pdfs    : {len(pdf_paths)}")
    print(f"[INFO] output_root : {args.output_root.resolve()}")

    success_count = 0
    failed: list[tuple[str, str]] = []

    for pdf_path in pdf_paths:
        doc_id = slugify_doc_id(pdf_path.stem)
        print(f"\n[RUN] {pdf_path.name} -> {doc_id}")
        try:
            document = run_stage1(
                input_path=pdf_path,
                project_root=PROJECT_ROOT,
                output_root=args.output_root,
                doc_id=doc_id,
                dpi=args.dpi,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            failed.append((pdf_path.name, str(exc)))
            print(f"[FAIL] {pdf_path.name}: {exc}")
            continue

        success_count += 1
        print(
            f"[OK] {document.source_file} -> {document.doc_id} "
            f"({document.num_pages} page(s), has_text_layer={document.has_text_layer})"
        )

    print("\n[SUMMARY]")
    print(f"  total   : {len(pdf_paths)}")
    print(f"  success : {success_count}")
    print(f"  failed  : {len(failed)}")

    if failed:
        print("\n[FAILED FILES]")
        for name, reason in failed:
            print(f"  - {name}: {reason}")


if __name__ == "__main__":
    main()
