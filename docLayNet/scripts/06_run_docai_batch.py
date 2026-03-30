from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
SCRIPTS = ROOT / "scripts"
IMAGES_DIR = ROOT / "outputs" / "images"
OUT_BASE = ROOT / "outputs" / "docai_raw"

RUN_ONE_SCRIPT = SCRIPTS / "06a_docai_infer.py"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--processor",
        required=True,
        choices=["ocr", "form", "layout"],
        help="Document AI processor type",
    )
    ap.add_argument(
        "--input_dir",
        type=Path,
        default=IMAGES_DIR,
        help="Directory containing input images (default: outputs/images)",
    )
    ap.add_argument(
        "--output_base",
        type=Path,
        default=OUT_BASE,
        help="Base output directory (default: outputs/docai)",
    )
    ap.add_argument(
        "--pattern",
        type=str,
        default="*.png",
        help="Glob pattern for input files (default: *.png)",
    )
    ap.add_argument(
        "--fail_fast",
        action="store_true",
        help="Stop immediately when one file fails",
    )
    return ap.parse_args()


def run_one(
    image_path: Path,
    processor: str,
    output_base: Path,
) -> tuple[int, str]:
    doc_id = image_path.stem
    output_dir = output_base / processor

    cmd = [
        sys.executable,
        str(RUN_ONE_SCRIPT),
        "--input",
        str(image_path),
        "--output_dir",
        str(output_dir),
        "--doc_id",
        doc_id,
        "--processor",
        processor,
    ]

    print("=" * 80)
    print(f"[RUN] doc_id={doc_id}, processor={processor}")
    print("[CMD]", " ".join(cmd))

    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode, doc_id


def main() -> None:
    args = parse_args()

    if not RUN_ONE_SCRIPT.exists():
        raise SystemExit(f"Missing script: {RUN_ONE_SCRIPT}")

    input_dir = args.input_dir
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    files = sorted(input_dir.glob(args.pattern))
    if not files:
        raise SystemExit(
            f"No files matched pattern {args.pattern!r} under {input_dir}"
        )

    print(f"[INFO] input_dir   = {input_dir}")
    print(f"[INFO] output_base = {args.output_base}")
    print(f"[INFO] processor   = {args.processor}")
    print(f"[INFO] pattern     = {args.pattern}")
    print(f"[INFO] total files = {len(files)}")

    ok_count = 0
    failed: list[str] = []

    for image_path in files:
        code, doc_id = run_one(
            image_path=image_path,
            processor=args.processor,
            output_base=args.output_base,
        )

        if code == 0:
            ok_count += 1
        else:
            failed.append(doc_id)
            print(f"[ERROR] failed doc_id={doc_id}, returncode={code}")
            if args.fail_fast:
                raise SystemExit(code)

    print("=" * 80)
    print(f"[SUMMARY] success = {ok_count}")
    print(f"[SUMMARY] failed  = {len(failed)}")

    if failed:
        print("[SUMMARY] failed doc_ids =", ", ".join(failed))
        raise SystemExit(1)

    print("[OK] all done")


if __name__ == "__main__":
    """
    python .\scripts\06_run_docai_batch.py --processor layout
    python .\scripts\06_run_docai_batch.py --processor ocr
    python .\scripts\06_run_docai_batch.py --processor form
    """
    main()

