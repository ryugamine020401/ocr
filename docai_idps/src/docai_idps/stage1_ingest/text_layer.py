from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from .models import CharArtifact, PageArtifact, PageTextArtifact, TextLayerArtifact, WordArtifact


def _round_box(value: float) -> float:
    return round(value, 2)


def _pdf_box_to_image_geometry(
    left: float,
    bottom: float,
    right: float,
    top: float,
    page_width_pts: float,
    page_height_pts: float,
    image_width: int,
    image_height: int,
) -> tuple[list[float], list[list[float]]]:
    scale_x = image_width / page_width_pts if page_width_pts else 1.0
    scale_y = image_height / page_height_pts if page_height_pts else 1.0

    x0 = left * scale_x
    x1 = right * scale_x
    y0 = (page_height_pts - top) * scale_y
    y1 = (page_height_pts - bottom) * scale_y

    bbox = [
        _round_box(x0),
        _round_box(y0),
        _round_box(max(x1 - x0, 1.0)),
        _round_box(max(y1 - y0, 1.0)),
    ]
    polygon = [
        [_round_box(x0), _round_box(y0)],
        [_round_box(x1), _round_box(y0)],
        [_round_box(x1), _round_box(y1)],
        [_round_box(x0), _round_box(y1)],
    ]
    return bbox, polygon


def _build_word_artifact(
    page_index: int,
    page_number: int,
    word_index: int,
    chars: list[dict],
) -> WordArtifact:
    xs0 = [item["left"] for item in chars]
    ys0 = [item["top"] for item in chars]
    xs1 = [item["right"] for item in chars]
    ys1 = [item["bottom"] for item in chars]

    left = min(xs0)
    top = min(ys0)
    right = max(xs1)
    bottom = max(ys1)

    bbox = [
        _round_box(left),
        _round_box(top),
        _round_box(max(right - left, 1.0)),
        _round_box(max(bottom - top, 1.0)),
    ]
    polygon = [
        [_round_box(left), _round_box(top)],
        [_round_box(right), _round_box(top)],
        [_round_box(right), _round_box(bottom)],
        [_round_box(left), _round_box(bottom)],
    ]

    return WordArtifact(
        word_id=f"p{page_number:04d}_w{word_index:06d}",
        page_index=page_index,
        page_number=page_number,
        text="".join(item["text"] for item in chars),
        bbox=bbox,
        polygon=polygon,
        source="pdf_text_layer",
    )


def extract_text_layer(
    pdf_path: Path,
    rendered_pages: list[PageArtifact],
) -> TextLayerArtifact:
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages_text: list[PageTextArtifact] = []
    words: list[WordArtifact] = []
    chars: list[CharArtifact] = []

    try:
        for page_artifact in rendered_pages:
            page = pdf.get_page(page_artifact.page_index)
            textpage = page.get_textpage()

            try:
                page_text = textpage.get_text_range().replace("\x00", "")
                char_count = textpage.count_chars()
                page_width_pts = float(page.get_width())
                page_height_pts = float(page.get_height())
                current_word_chars: list[dict] = []
                page_word_count = 0

                for char_index in range(char_count):
                    char_text = textpage.get_text_range(char_index, 1).replace("\x00", "")
                    if not char_text:
                        continue

                    if char_text.isspace():
                        if current_word_chars:
                            page_word_count += 1
                            words.append(
                                _build_word_artifact(
                                    page_index=page_artifact.page_index,
                                    page_number=page_artifact.page_number,
                                    word_index=len(words) + 1,
                                    chars=current_word_chars,
                                )
                            )
                            current_word_chars = []
                        continue

                    left, bottom, right, top = textpage.get_charbox(char_index)
                    bbox, polygon = _pdf_box_to_image_geometry(
                        left=left,
                        bottom=bottom,
                        right=right,
                        top=top,
                        page_width_pts=page_width_pts,
                        page_height_pts=page_height_pts,
                        image_width=page_artifact.width,
                        image_height=page_artifact.height,
                    )

                    chars.append(
                        CharArtifact(
                            char_id=f"p{page_artifact.page_number:04d}_c{len(chars) + 1:06d}",
                            page_index=page_artifact.page_index,
                            page_number=page_artifact.page_number,
                            text=char_text,
                            bbox=bbox,
                            polygon=polygon,
                            source="pdf_text_layer",
                        )
                    )

                    current_word_chars.append(
                        {
                            "text": char_text,
                            "left": bbox[0],
                            "top": bbox[1],
                            "right": bbox[0] + bbox[2],
                            "bottom": bbox[1] + bbox[3],
                        }
                    )

                if current_word_chars:
                    page_word_count += 1
                    words.append(
                        _build_word_artifact(
                            page_index=page_artifact.page_index,
                            page_number=page_artifact.page_number,
                            word_index=len(words) + 1,
                            chars=current_word_chars,
                        )
                    )

                pages_text.append(
                    PageTextArtifact(
                        page_index=page_artifact.page_index,
                        page_number=page_artifact.page_number,
                        text=page_text,
                        source="pdf_text_layer" if page_text.strip() else "none",
                        text_length=len(page_text),
                        word_count=page_word_count,
                    )
                )
            finally:
                textpage.close()
                page.close()
    finally:
        pdf.close()

    full_text = "\n\n".join(page.text for page in pages_text).strip()
    has_text_layer = any(page.text.strip() for page in pages_text)

    return TextLayerArtifact(
        full_text=full_text,
        pages_text=pages_text,
        words=words,
        chars=chars,
        has_text_layer=has_text_layer,
        text_source="pdf_text_layer" if has_text_layer else "none",
    )
