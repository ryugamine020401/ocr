from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import DocumentArtifact, IngestMetadata
from .pdf_reader import read_pdf_info
from .rasterize import render_pdf_pages
from .text_layer import extract_text_layer


def slugify_doc_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized or "document"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_stage1(
    input_path: Path,
    project_root: Path,
    output_root: Path | None = None,
    doc_id: str | None = None,
    dpi: int = 200,
    overwrite: bool = False,
) -> DocumentArtifact:
    input_path = input_path.resolve()
    project_root = project_root.resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")
    if input_path.suffix.lower() != ".pdf":
        raise ValueError(f"Stage 1 only supports PDF input right now: {input_path.name}")
    if dpi <= 0:
        raise ValueError("dpi must be a positive integer")

    resolved_doc_id = slugify_doc_id(doc_id or input_path.stem)
    resolved_output_root = (
        output_root.resolve()
        if output_root is not None
        else project_root / "data" / "outputs" / "stage1_ingest"
    )
    doc_output_dir = resolved_output_root / resolved_doc_id
    pages_dir = doc_output_dir / "pages"
    text_dir = doc_output_dir / "text"
    meta_dir = doc_output_dir / "meta"
    created_at = datetime.now(timezone.utc).isoformat()

    if doc_output_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Output directory already exists: {doc_output_dir}. "
                "Use overwrite=True to replace it."
            )

    pdf_info = read_pdf_info(input_path)
    pages = render_pdf_pages(
        pdf_path=input_path,
        pages_dir=pages_dir,
        project_root=project_root,
        dpi=dpi,
    )

    if len(pages) != pdf_info.page_count:
        raise RuntimeError(
            f"Rendered page count mismatch: expected {pdf_info.page_count}, got {len(pages)}"
        )

    for page_number, page in enumerate(pages, start=1):
        page.page_number = page_number

    text_layer = extract_text_layer(
        pdf_path=input_path,
        rendered_pages=pages,
    )

    page_index_to_text = {item.page_index: item for item in text_layer.pages_text}
    for page in pages:
        page_text = page_index_to_text.get(page.page_index)
        if page_text is None:
            continue
        page.text_length = page_text.text_length
        page.word_count = page_text.word_count

    document = DocumentArtifact(
        doc_id=resolved_doc_id,
        source_file=input_path.name,
        source_path=input_path.relative_to(project_root).as_posix(),
        mime_type=pdf_info.mime_type,
        file_size_bytes=pdf_info.file_size_bytes,
        sha256=pdf_info.sha256,
        num_pages=pdf_info.page_count,
        dpi=dpi,
        created_at=created_at,
        text_source=text_layer.text_source,
        has_text_layer=text_layer.has_text_layer,
        pages=pages,
    )
    metadata = IngestMetadata(
        doc_id=resolved_doc_id,
        input_path=input_path.relative_to(project_root).as_posix(),
        output_dir=doc_output_dir.relative_to(project_root).as_posix(),
        dpi=dpi,
        num_pages=pdf_info.page_count,
        has_text_layer=text_layer.has_text_layer,
        text_source=text_layer.text_source,
        num_words=len(text_layer.words),
        num_chars=len(text_layer.chars),
        created_at=created_at,
    )

    write_json(doc_output_dir / "document.json", document.to_dict())
    text_dir.mkdir(parents=True, exist_ok=True)
    (text_dir / "full_text.txt").write_text(text_layer.full_text, encoding="utf-8")
    write_json(
        text_dir / "pages_text.json",
        [item.to_dict() for item in text_layer.pages_text],
    )
    write_json(
        text_dir / "words.json",
        [item.to_dict() for item in text_layer.words],
    )
    write_json(
        text_dir / "chars.json",
        [item.to_dict() for item in text_layer.chars],
    )
    write_json(meta_dir / "ingest.json", metadata.to_dict())

    return document
