from __future__ import annotations

import json
import sys
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python 06a_docling_infer.py <input_image> <output_json>"
        )

    input_path = Path(sys.argv[1]).resolve()
    output_json = Path(sys.argv[2]).resolve()

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    output_json.parent.mkdir(parents=True, exist_ok=True)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(
        device=AcceleratorDevice.CUDA,
        num_threads=4,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.IMAGE: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )

    print(f"[INFO] input : {input_path}")
    print(f"[INFO] output: {output_json}")
    print("[INFO] accelerator: CUDA")

    result = converter.convert(str(input_path))
    doc_dict = result.document.export_to_dict()

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(doc_dict, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {output_json}")


if __name__ == "__main__":
    main()