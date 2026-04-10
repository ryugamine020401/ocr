from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from .models import PageArtifact


def render_pdf_pages(
    pdf_path: Path,
    pages_dir: Path,
    project_root: Path,
    dpi: int,
) -> list[PageArtifact]:
    try:
        import PIL.Image  # noqa: F401
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Pillow is required for Stage 1 rasterization. "
            "Install it with `pipenv install pillow`."
        ) from exc

    pages_dir.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72.0
    artifacts: list[PageArtifact] = []

    try:
        for page_index in range(len(pdf)):
            page = pdf.get_page(page_index)
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()

                out_path = pages_dir / f"{page_index + 1:04d}.png"
                image.save(out_path)

                artifacts.append(
                    PageArtifact(
                        page_index=page_index,
                        page_number=page_index + 1,
                        image_path=out_path.resolve().relative_to(
                            project_root.resolve()
                        ).as_posix(),
                        width=image.width,
                        height=image.height,
                    )
                )
            finally:
                page.close()
    finally:
        pdf.close()

    return artifacts
