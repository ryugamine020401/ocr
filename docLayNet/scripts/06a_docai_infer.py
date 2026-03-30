from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
PROJECT_ROOT = ROOT.parent                   # .../ocr
DOCAI_EVAL_ROOT = PROJECT_ROOT / "docai_eval"


def get_docai_python() -> Path:
    if os.name == "nt":
        py = DOCAI_EVAL_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        py = DOCAI_EVAL_ROOT / ".venv" / "bin" / "python"
    return py.resolve()


def ensure_docai_venv() -> None:
    target_python = get_docai_python()
    current_python = Path(sys.executable).resolve()

    if not target_python.exists():
        raise SystemExit(
            f"DocAI venv python not found: {target_python}\n"
            f"Please create/install the venv under: {DOCAI_EVAL_ROOT / '.venv'}"
        )

    if current_python != target_python:
        print(f"[INFO] current python = {current_python}")
        print(f"[INFO] relaunch with  = {target_python}")

        result = subprocess.run(
            [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            cwd=str(ROOT),
            env=os.environ.copy(),
        )
        raise SystemExit(result.returncode)

    print(f"[INFO] using python   = {current_python}")


ensure_docai_venv()

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.protobuf.json_format import MessageToDict
from PIL import Image


PROCESSOR_ENV_MAP = {
    "ocr": "GCP_OCR_PROCESSOR_ID",
    "form": "GCP_FORM_PROCESSOR_ID",
    "layout": "GCP_LAYOUT_PROCESSOR_ID",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output_dir", required=True, type=Path)
    ap.add_argument("--doc_id", required=True, type=str)
    ap.add_argument(
        "--processor",
        required=True,
        choices=["ocr", "form", "layout"],
        help="Document AI processor type",
    )
    return ap.parse_args()


def load_env() -> None:
    env_path = DOCAI_EVAL_ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(f"Missing .env: {env_path}")

    load_dotenv(env_path)

    cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred:
        cred_path = Path(cred)
        if not cred_path.is_absolute():
            cred_path = (DOCAI_EVAL_ROOT / cred_path).resolve()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)

        if not cred_path.exists():
            raise SystemExit(
                f"Credential file not found: {cred_path}\n"
                f"Original env GOOGLE_APPLICATION_CREDENTIALS={cred!r}"
            )

        print(f"[INFO] GOOGLE_APPLICATION_CREDENTIALS = {cred_path}")


def get_client(location: str):
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    return documentai.DocumentProcessorServiceClient(client_options=opts)


def detect_mime_type(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".png":
        return "image/png"
    if suf in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suf == ".pdf":
        return "application/pdf"
    raise SystemExit(f"Unsupported suffix: {path.name}")


def convert_image_to_pdf_bytes(image_path: Path) -> bytes:
    img = Image.open(image_path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def get_processor_id(processor_name: str) -> str:
    env_key = PROCESSOR_ENV_MAP[processor_name]
    processor_id = os.getenv(env_key, "").strip()
    if not processor_id:
        raise SystemExit(
            f"Missing processor id for '{processor_name}'. "
            f"Please set {env_key} in {DOCAI_EVAL_ROOT / '.env'}"
        )
    return processor_id


def main() -> None:
    args = parse_args()
    load_env()

    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    location = os.getenv("GCP_LOCATION", "").strip()
    processor_id = get_processor_id(args.processor)

    if not project_id:
        raise SystemExit("Missing env: GCP_PROJECT_ID")
    if not location:
        raise SystemExit("Missing env: GCP_LOCATION")

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.processor == "layout":
        mime_type = "application/pdf"
        content = convert_image_to_pdf_bytes(args.input)
    else:
        mime_type = detect_mime_type(args.input)
        content = args.input.read_bytes()

    print(f"[INFO] doc_id       = {args.doc_id}")
    print(f"[INFO] processor    = {args.processor}")
    print(f"[INFO] processor_id = {processor_id}")
    print(f"[INFO] input        = {args.input}")
    print(f"[INFO] mime_type    = {mime_type}")
    print(f"[INFO] start process_document")

    client = get_client(location)
    processor_name = client.processor_path(project_id, location, processor_id)

    raw_document = documentai.RawDocument(
        content=content,
        mime_type=mime_type,
    )

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=raw_document,
    )

    response = client.process_document(request=request, timeout=150)
    document = response.document

    print(f"[INFO] finish process_document")

    raw_dict = MessageToDict(
        document._pb,
        preserving_proto_field_name=True,
    )

    out_json = args.output_dir / f"{args.doc_id}.json"
    out_json.write_text(
        json.dumps(raw_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    out_txt = args.output_dir / f"{args.doc_id}.txt"
    out_txt.write_text((document.text or "").strip(), encoding="utf-8")

    print(f"[OK] doc_id={args.doc_id}")
    print(f"[OK] json={out_json}")
    print(f"[OK] txt ={out_txt}")


if __name__ == "__main__":
    main()