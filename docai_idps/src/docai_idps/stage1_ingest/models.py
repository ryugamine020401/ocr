from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class PageArtifact:
    page_index: int
    page_number: int
    image_path: str
    width: int
    height: int
    text_length: int = 0
    word_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DocumentArtifact:
    doc_id: str
    source_file: str
    source_path: str
    mime_type: str
    file_size_bytes: int
    sha256: str
    num_pages: int
    dpi: int
    created_at: str
    text_source: str
    has_text_layer: bool
    pages: list[PageArtifact]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["pages"] = [page.to_dict() for page in self.pages]
        return data


@dataclass(slots=True)
class IngestMetadata:
    doc_id: str
    input_path: str
    output_dir: str
    dpi: int
    num_pages: int
    has_text_layer: bool
    text_source: str
    num_words: int
    num_chars: int
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PdfInfo:
    page_count: int
    file_size_bytes: int
    sha256: str
    mime_type: str = "application/pdf"


@dataclass(slots=True)
class PageTextArtifact:
    page_index: int
    page_number: int
    text: str
    source: str
    text_length: int
    word_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class WordArtifact:
    word_id: str
    page_index: int
    page_number: int
    text: str
    bbox: list[float]
    polygon: list[list[float]]
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class CharArtifact:
    char_id: str
    page_index: int
    page_number: int
    text: str
    bbox: list[float]
    polygon: list[list[float]]
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TextLayerArtifact:
    full_text: str
    pages_text: list[PageTextArtifact]
    words: list[WordArtifact]
    chars: list[CharArtifact]
    has_text_layer: bool
    text_source: str
