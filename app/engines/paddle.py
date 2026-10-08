"""PaddleOCR (lang="tg" -> multilingual Cyrillic model). Optional: uv sync --extra paddle"""

import os
import threading
from pathlib import Path

import numpy as np

from app.config import Settings
from app.engines.base import TAJIK_EXTRA_LETTERS, Line


class PaddleEngine:
    name = "paddle"

    def __init__(self, settings: Settings):
        # Skip the slow "which model host is reachable" check on every start
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        try:
            from paddleocr import PaddleOCR  # heavy import, keep it lazy
        except ImportError as e:
            raise RuntimeError("PaddleOCR не установлен: uv sync --extra paddle") from e

        self.settings = settings
        kwargs = dict(
            lang=settings.lang,
            device=settings.device,
            enable_mkldnn=settings.enable_mkldnn,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=settings.use_textline_orientation,
            text_recognition_model_name=settings.rec_model_name,
            text_recognition_model_dir=settings.rec_model_dir,
            text_detection_model_name=settings.det_model_name,
            text_detection_model_dir=settings.det_model_dir,
        )
        self._ocr = PaddleOCR(**{k: v for k, v in kwargs.items() if v is not None})
        # The Paddle predictor is not thread-safe: one inference at a time
        self._lock = threading.Lock()

    def recognize(self, image_bgr: np.ndarray) -> list[Line]:
        with self._lock:
            results = self._ocr.predict(image_bgr)
        lines: list[Line] = []
        for res in results:
            for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"], strict=False):
                if not text.strip():
                    continue
                lines.append(
                    Line(text=text, score=round(float(score), 4), box=np.asarray(poly).astype(int).tolist())
                )
        return lines

    def info(self) -> dict:
        """Which recognition model is loaded and whether its dictionary covers Tajik letters."""
        info: dict = {"engine": self.name, "lang": self.settings.lang, "device": self.settings.device}
        try:
            cfg = self._ocr.paddlex_pipeline.text_rec_model  # internal API, best-effort
            info["rec_model"] = getattr(cfg, "model_name", None)
            chars = set(getattr(cfg.post_op, "character", []) or [])
        except Exception:
            chars = set()
        if not chars:
            chars = _chars_from_model_dir(self.settings.rec_model_dir, info.get("rec_model"))
        if chars:
            info["dict_size"] = len(chars)
            info["tajik_letters_missing"] = "".join(c for c in TAJIK_EXTRA_LETTERS if c not in chars)
        return info


def _chars_from_model_dir(model_dir: str | None, model_name: str | None) -> set[str]:
    """Read the character dictionary from the model's inference.yml."""
    import yaml

    if model_dir:
        path = Path(model_dir) / "inference.yml"
    elif model_name:
        cache = Path(os.getenv("PADDLE_PDX_CACHE_HOME", Path.home() / ".paddlex"))
        path = cache / "official_models" / model_name / "inference.yml"
    else:
        return set()
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return set(data.get("PostProcess", {}).get("character_dict", []) or [])
