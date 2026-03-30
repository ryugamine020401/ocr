from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]   # .../ocr/docLayNet
PROJECT_ROOT = ROOT.parent                   # .../ocr


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output_dir", required=True, type=Path)
    ap.add_argument("--doc_id", required=True)
    return ap.parse_args()


def _build_candidate_commands(input_path: Path, tmp_dir: Path) -> list[list[str]]:
    """
    依照目前 venv 內已存在的 mineru.exe 建立候選指令。
    目前已知 mineru 需要 -p / --path，因此優先用這組參數。
    """
    py_exe = Path(sys.executable)
    scripts_dir = py_exe.parent

    mineru_exe_candidates = [
        scripts_dir / "mineru.exe",
        scripts_dir / "mineru",
    ]

    cmds: list[list[str]] = []

    for exe in mineru_exe_candidates:
        if exe.exists():
            # 先嘗試最可能正確的 CLI 參數
            cmds.append([str(exe), "-p", str(input_path), "-o", str(tmp_dir)])
            cmds.append([str(exe), "--path", str(input_path), "--output", str(tmp_dir)])
            cmds.append([str(exe), "--path", str(input_path), "-o", str(tmp_dir)])

    return cmds


def run_mineru_command(input_path: Path, tmp_dir: Path) -> list[str]:
    cmds = _build_candidate_commands(input_path, tmp_dir)

    if not cmds:
        raise RuntimeError(
            "No MinerU executable found in current venv.\n"
            f"python executable: {sys.executable}"
        )

    last_error: Exception | None = None

    print(f"[INFO] sys.executable = {sys.executable}")

    for cmd in cmds:
        try:
            print(f"[TRY] {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            print("[OK] MinerU command succeeded")
            return cmd
        except Exception as e:
            print(f"[WARN] command failed: {' '.join(cmd)}")
            print(f"[WARN] {type(e).__name__}: {e}")
            last_error = e

    raise RuntimeError(
        "Unable to run MinerU entrypoint from current venv.\n"
        "The mineru executable exists, but the CLI arguments still do not match the installed version."
    ) from last_error


def pick_primary_json(tmp_dir: Path) -> Path:
    json_files = sorted(tmp_dir.rglob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON output found under {tmp_dir}")

    preferred_suffixes = [
        "_middle.json",
        "_content_list.json",
        "_content_list_v2.json",
        "_model.json",
        ".json",
    ]

    for suffix in preferred_suffixes:
        matched = [p for p in json_files if p.name.lower().endswith(suffix)]
        if matched:
            return matched[0]

    return json_files[0]


def main() -> None:
    args = parse_args()
    input_path: Path = args.input
    output_dir: Path = args.output_dir
    doc_id: str = args.doc_id

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    tmp_dir = output_dir / "_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"[INFO] input       : {input_path}")
    print(f"[INFO] output_dir  : {output_dir}")
    print(f"[INFO] tmp_dir     : {tmp_dir}")
    print(f"[INFO] doc_id      : {doc_id}")

    used_cmd = run_mineru_command(input_path, tmp_dir)

    primary_json = pick_primary_json(tmp_dir)
    final_json = output_dir / f"{doc_id}.json"
    shutil.copy2(primary_json, final_json)

    meta = {
        "doc_id": doc_id,
        "project_root": str(PROJECT_ROOT),
        "python_executable": sys.executable,
        "used_command": used_cmd,
        "input": str(input_path),
        "primary_json": str(primary_json),
        "saved_json": str(final_json),
    }

    with (output_dir / "_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[OK] saved: {final_json}")


if __name__ == "__main__":
    main()