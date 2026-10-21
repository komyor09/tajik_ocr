"""Shared Tesseract plumbing: binary and model check at startup, OCR of one image region."""

import os
import shutil
from pathlib import Path

import numpy as np
import pytesseract
from pytesseract import Output

WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")  # local development on Windows

# tgk - Tajik text, eng - Latin text on the card, ocrb - MRZ font
PASSPORT_LANGS = ("tgk", "eng", "ocrb")


def init(cmd: str | None, tessdata_dir: str, langs: set[str]) -> str:
    """Find the tesseract binary and check the models. Called once at startup. Returns the version.

    Raises RuntimeError with a clear message if something is missing.
    """
    cmd = cmd or shutil.which("tesseract") or (str(WINDOWS_DEFAULT) if WINDOWS_DEFAULT.exists() else None)
    if not cmd:
        raise RuntimeError("Tesseract не найден: установите его или укажите путь в TESSERACT_CMD")
    pytesseract.pytesseract.tesseract_cmd = cmd

    models = Path(tessdata_dir).resolve()
    missing = [lang for lang in sorted(langs) if not (models / f"{lang}.traineddata").is_file()]
    if missing:
        raise RuntimeError(
            f"Нет моделей Tesseract в {models}: {', '.join(missing)}. "
            "Скачайте их: python scripts/download_models.py (см. DEPLOY.md)"
        )
    # Tesseract reads models from TESSDATA_PREFIX; every tesseract process started later inherits it
    os.environ["TESSDATA_PREFIX"] = str(models)
    return str(pytesseract.get_tesseract_version())


def read(
    image: np.ndarray, lang: str, psm: int = 7, whitelist: str | None = None
) -> tuple[str, float, list[dict]]:
    """OCR an image (gray or BGR). Returns (text with \\n between lines, mean confidence 0..1, words).

    `whitelist` must be ASCII: on Windows non-ASCII command-line args can be mangled.
    """
    if whitelist is not None and not whitelist.isascii():
        raise ValueError("whitelist must be ASCII")
    config = f"--psm {psm}"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"
    if image.ndim == 3:
        image = image[:, :, ::-1]  # BGR -> RGB
    data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=Output.DICT)

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
