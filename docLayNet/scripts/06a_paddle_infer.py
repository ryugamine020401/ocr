from __future__ import annotations

import json
import sys
from pathlib import Path

from paddleocr import PaddleOCR


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python 06a_paddle_infer.py <input_image> <output_json>"
        )

    input_path = Path(sys.argv[1]).resolve()
    output_json = Path(sys.argv[2]).resolve()

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    output_json.parent.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] input : {input_path}")
    print(f"[INFO] output: {output_json}")

    ocr = PaddleOCR(
        use_textline_orientation=True,
        lang="en",
    )
    result = ocr.predict(str(input_path))

    blocks = []

    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                texts = item.get("rec_texts", [])
                scores = item.get("rec_scores", [])
                polys = item.get("dt_polys", [])

                for text, score, poly in zip(texts, scores, polys):
                    if not text:
                        continue

                    xs = [float(p[0]) for p in poly]
                    ys = [float(p[1]) for p in poly]

                    x1, y1 = float(min(xs)), float(min(ys))
                    x2, y2 = float(max(xs)), float(max(ys))

                    blocks.append({
                        "type": "text",
                        "bbox": [x1, y1, x2, y2],
                        "text": str(text),
                        "score": float(score),
                    })
    doc_dict = {
        "blocks": blocks,
        "image": {
            "path": str(input_path),
        }
    }

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(doc_dict, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {output_json}")


if __name__ == "__main__":
    main()