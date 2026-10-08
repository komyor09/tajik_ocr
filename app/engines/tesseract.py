"""Tesseract with the official Tajik model (tgk.traineddata)."""

import numpy as np

from app import tess
from app.config import Settings
from app.engines.base import Line


class TesseractEngine:
    name = "tesseract"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.version = tess.init(settings.tesseract_cmd)
        self.models = tess.langs_location(settings.tesseract_lang)  # raises if a model is missing

    def recognize(self, image_bgr: np.ndarray) -> list[Line]:
        _, _, words = tess.read(image_bgr, self.settings.tesseract_lang, psm=self.settings.tesseract_psm)
        return _group_lines(words)

    def info(self) -> dict:
        return {
            "engine": self.name,
            "version": self.version,
            "lang": self.settings.tesseract_lang,
            "models": self.models,
            "psm": self.settings.tesseract_psm,
        }


def _group_lines(words: list[dict]) -> list[Line]:
    """Tesseract's own (block, paragraph, line) grouping keeps columns apart."""
    lines: dict[tuple, list[dict]] = {}
    for w in words:
        lines.setdefault(w["line"], []).append(w)
    result = []
    for ws in lines.values():
        x1 = min(w["box"][0] for w in ws)
        y1 = min(w["box"][1] for w in ws)
        x2 = max(w["box"][0] + w["box"][2] for w in ws)
        y2 = max(w["box"][1] + w["box"][3] for w in ws)
        result.append(
            Line(
                text=" ".join(w["text"] for w in ws),
                score=round(sum(w["conf"] for w in ws) / len(ws), 4),
                box=[[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            )
        )
    return result
