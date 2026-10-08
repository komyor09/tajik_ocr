"""Shared Tesseract plumbing: binary lookup, model directory, OCR of one image region."""

import os
import shutil
import threading
from pathlib import Path

import numpy as np
import pytesseract
from pytesseract import Output

# Project-local models (tgk/eng from tessdata_best, ocrb for MRZ): scripts/download_models.py
MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "tessdata"
WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

_init_lock = threading.Lock()
_version: str | None = None


def init(cmd_override: str | None = None) -> str:
    """Find the tesseract binary once. Returns its version."""
    global _version
    with _init_lock:
        if _version:
            return _version
        cmd = cmd_override or shutil.which("tesseract")
        if not cmd and WINDOWS_DEFAULT.exists():
            cmd = str(WINDOWS_DEFAULT)
        if not cmd:
            raise RuntimeError(
                "Tesseract не найден. Установи его (https://github.com/UB-Mannheim/tesseract/wiki) "
                "или укажи путь в TESSERACT_CMD."
            )
        pytesseract.pytesseract.tesseract_cmd = cmd
        _version = str(pytesseract.get_tesseract_version())
        return _version


def _models_arg() -> str | None:
    """'--tessdata-dir <relative path>' if project models exist.

    The path is relative to the working directory on purpose: pytesseract cannot pass paths
    with spaces on Windows (e.g. 'Desktop\\tajik ocr').
    """
    if not MODELS_DIR.is_dir():
        return None
    try:
        rel = os.path.relpath(MODELS_DIR)
    except ValueError:  # different drive on Windows
        return None
    if " " in rel:
        return None
    return f"--tessdata-dir {rel.replace(os.sep, '/')}"


def _project_langs() -> set[str]:
    if not _models_arg():
        return set()
    return {p.stem for p in MODELS_DIR.glob("*.traineddata")}


def langs_location(lang: str) -> str:
    """'project' | 'system' | raises if a language is missing everywhere."""
    parts = lang.split("+")
    if all(p in _project_langs() for p in parts):
        return "project"
    system = set(pytesseract.get_languages(config=""))
    missing = [p for p in parts if p not in system]
    if missing:
        raise RuntimeError(
            f"Нет моделей Tesseract: {', '.join(missing)}. Запусти: uv run python scripts/download_models.py"
        )
    return "system"


def read(
    image: np.ndarray, lang: str, psm: int = 7, whitelist: str | None = None
) -> tuple[str, float, list[dict]]:
    """OCR an image (gray or BGR). Returns (text with \\n between lines, mean confidence 0..1, words).

    `whitelist` must be ASCII: on Windows non-ASCII command-line args can be mangled.
    """
    if whitelist is not None and not whitelist.isascii():
        raise ValueError("whitelist must be ASCII")
    config = [f"--psm {psm}"]
    if langs_location(lang) == "project":
        config.insert(0, _models_arg())
    if whitelist:
        config.append(f"-c tessedit_char_whitelist={whitelist}")
    if image.ndim == 3:
        image = image[:, :, ::-1]  # BGR -> RGB
    data = pytesseract.image_to_data(image, lang=lang, config=" ".join(config), output_type=Output.DICT)

    words, lines = [], {}
    for i, text in enumerate(data["text"]):
        if not text.strip() or float(data["conf"][i]) < 0:
            continue
        w = {
            "text": text,
            "conf": float(data["conf"][i]) / 100,
            "box": (data["left"][i], data["top"][i], data["width"][i], data["height"][i]),
            "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
        }
        words.append(w)
        lines.setdefault(w["line"], []).append(text)
    text = "\n".join(" ".join(ws) for ws in lines.values())
    conf = sum(w["conf"] for w in words) / len(words) if words else 0.0
    return text, round(conf, 4), words
