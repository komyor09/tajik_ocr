"""Settings, read from environment variables (or a .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _opt(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    engine: str  # default engine: "tesseract" | "paddle"
    flatten: bool  # even out uneven lighting before OCR
    deskew: bool  # straighten slightly rotated text (up to 15 degrees)
    min_score: float
    max_upload_mb: int

    # --- Tesseract ---
    tesseract_cmd: str | None  # path to tesseract.exe if it is not on PATH
    tesseract_lang: str  # "tgk", or "tgk+rus" for mixed text
    tesseract_psm: int  # page segmentation mode: 3 = auto layout, 6 = one text block

    # --- PaddleOCR ---
    lang: str  # "tg" -> cyrillic_PP-OCRv5_mobile_rec
    device: str  # "cpu" or "gpu:0"
    rec_model_name: str | None
    rec_model_dir: str | None
    det_model_name: str | None
    det_model_dir: str | None
    enable_mkldnn: bool
    use_textline_orientation: bool


def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        engine=os.getenv("OCR_ENGINE", "tesseract").strip().lower(),
        flatten=_bool("OCR_FLATTEN", True),
        deskew=_bool("OCR_DESKEW", True),
        min_score=float(os.getenv("OCR_MIN_SCORE", "0.0")),
        max_upload_mb=int(os.getenv("OCR_MAX_UPLOAD_MB", "15")),
        tesseract_cmd=_opt("TESSERACT_CMD"),
        tesseract_lang=os.getenv("TESSERACT_LANG", "tgk"),
        tesseract_psm=int(os.getenv("TESSERACT_PSM", "3")),
        lang=os.getenv("OCR_LANG", "tg"),
        device=os.getenv("OCR_DEVICE", "cpu"),
        rec_model_name=_opt("OCR_REC_MODEL_NAME"),
        rec_model_dir=_opt("OCR_REC_MODEL_DIR"),
        det_model_name=_opt("OCR_DET_MODEL_NAME"),
        det_model_dir=_opt("OCR_DET_MODEL_DIR"),
        enable_mkldnn=_bool("OCR_ENABLE_MKLDNN", False),
        use_textline_orientation=_bool("OCR_TEXTLINE_ORIENTATION", False),
    )
