from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from .models import PdfInfo


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_pdf_info(pdf_path: Path) -> PdfInfo:
    reader = PdfReader(str(pdf_path))
    return PdfInfo(
        page_count=len(reader.pages),
        file_size_bytes=pdf_path.stat().st_size,
        sha256=compute_sha256(pdf_path),
    )
