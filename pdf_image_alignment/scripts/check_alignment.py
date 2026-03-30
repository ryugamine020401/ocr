from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "1_origin.pdf"
IMG_PATH = ROOT / "1.png"
OUT_DIR = ROOT / "outputs"

PAGE_INDEX = 0
ZOOM = 2.0


def render_pdf_page(pdf_path: Path, page_index: int, zoom: float):
    doc = fitz.open(pdf_path)
    page = doc[page_index]

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    return doc, page, img


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")
    if not IMG_PATH.exists():
        raise FileNotFoundError(f"Image not found: {IMG_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    doc, page, rendered_img = render_pdf_page(PDF_PATH, PAGE_INDEX, ZOOM)
    target_img = Image.open(IMG_PATH).convert("RGB")

    rendered_path = OUT_DIR / "rendered_from_pdf.png"
    rendered_img.save(rendered_path)

    pdf_rect = page.rect
    pdf_w = float(pdf_rect.width)
    pdf_h = float(pdf_rect.height)

    render_w, render_h = rendered_img.size
    img_w, img_h = target_img.size

    scale_x = img_w / pdf_w
    scale_y = img_h / pdf_h

    print("=" * 80)
    print(f"PDF path      : {PDF_PATH}")
    print(f"Image path    : {IMG_PATH}")
    print(f"Page index    : {PAGE_INDEX}")
    print(f"PDF size      : ({pdf_w:.2f}, {pdf_h:.2f}) points")
    print(f"Rendered size : ({render_w}, {render_h}) px  [zoom={ZOOM}]")
    print(f"Target size   : ({img_w}, {img_h}) px")
    print(f"scale_x       : {scale_x:.6f}")
    print(f"scale_y       : {scale_y:.6f}")
    print("=" * 80)

    # 先畫一個假的 PDF bbox 測試投影
    pdf_bbox = (100.0, 100.0, 300.0, 220.0)  # (x0, y0, x1, y1)

    x0, y0, x1, y1 = pdf_bbox
    img_bbox = (
        x0 * scale_x,
        y0 * scale_y,
        x1 * scale_x,
        y1 * scale_y,
    )

    overlay = target_img.copy()
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(img_bbox, outline="red", width=3)

    overlay_path = OUT_DIR / "overlay_test_bbox.png"
    overlay.save(overlay_path)

    print(f"Fake PDF bbox : {pdf_bbox}")
    print(
        "Mapped IMG bbox: "
        f"({img_bbox[0]:.2f}, {img_bbox[1]:.2f}, {img_bbox[2]:.2f}, {img_bbox[3]:.2f})"
    )
    print(f"Saved rendered image to: {rendered_path}")
    print(f"Saved overlay image  to: {overlay_path}")

    doc.close()


if __name__ == "__main__":
    main()