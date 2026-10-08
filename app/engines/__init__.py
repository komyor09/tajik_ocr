"""OCR engines behind one interface. Each is loaded lazily, once, on first use."""

import threading

from app.config import Settings
from app.engines.base import Line, OcrEngine

ENGINES = ("tesseract", "paddle")

_cache: dict[str, OcrEngine] = {}
_lock = threading.Lock()


def get_engine(name: str, settings: Settings) -> OcrEngine:
    if name not in ENGINES:
        raise ValueError(f"Unknown engine '{name}'. Available: {', '.join(ENGINES)}")
    with _lock:
        if name not in _cache:
            if name == "tesseract":
                from app.engines.tesseract import TesseractEngine as cls
            else:
                from app.engines.paddle import PaddleEngine as cls
            _cache[name] = cls(settings)
        return _cache[name]


def loaded_engines() -> dict[str, OcrEngine]:
    return dict(_cache)


__all__ = ["ENGINES", "Line", "OcrEngine", "get_engine", "loaded_engines"]
