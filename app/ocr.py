"""POST /ocr: any Tajik text on an image (Tesseract, model tgk)."""

import time

import numpy as np
from fastapi import APIRouter, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app import tess
from app.config import get_settings
from app.images import load_upload
from app.preprocess import deskew as deskew_image
from app.preprocess import flatten_lighting

router = APIRouter(tags=["ocr"])
settings = get_settings()


class LineOut(BaseModel):
    text: str
    score: float = Field(description="Уверенность 0..1")
    box: list[list[int]] = Field(description="4 точки [x, y] по часовой стрелке от левого верхнего угла")


class OcrResponse(BaseModel):
    text: str = Field(description="Весь текст, строки через \\n")
    lines: list[LineOut]
    width: int
    height: int
    deskew_angle: float = Field(description="Угол выпрямления; координаты box — на выпрямленном изображении")
    elapsed_ms: int


def _recognize(image: np.ndarray, flatten: bool, deskew: bool) -> tuple[list[LineOut], float]:
    """CPU-heavy part: preprocessing + Tesseract. Runs in a worker thread."""
    angle = 0.0
    if flatten:
        image = flatten_lighting(image)
    if deskew:
        image, angle = deskew_image(image)
    _, _, words = tess.read(image, settings.tesseract_lang, psm=settings.tesseract_psm)
    return _group_lines(words), angle


def _group_lines(words: list[dict]) -> list[LineOut]:
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
            LineOut(
                text=" ".join(w["text"] for w in ws),
                score=round(sum(w["conf"] for w in ws) / len(ws), 4),
                box=[[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            )
        )
    return result


@router.post(
    "/ocr",
    response_model=OcrResponse,
    summary="Распознать таджикский текст на изображении",
    responses={413: {"description": "Файл больше MAX_UPLOAD_MB"}, 415: {"description": "Не изображение"}},
)
async def ocr(
    file: UploadFile = File(..., description="Изображение с текстом: JPG, PNG, WEBP, BMP, TIFF"),
    flatten: bool | None = Query(None, description="Выравнивать освещение; по умолчанию OCR_FLATTEN"),
    deskew: bool | None = Query(None, description="Выпрямлять наклон до 15°; по умолчанию OCR_DESKEW"),
    min_score: float | None = Query(None, ge=0, le=1, description="Отбросить строки с уверенностью ниже"),
):
    image, width, height = await load_upload(file, settings.max_upload_mb)
    started = time.perf_counter()
    lines, angle = await run_in_threadpool(
        _recognize,
        image,
        settings.ocr_flatten if flatten is None else flatten,
        settings.ocr_deskew if deskew is None else deskew,
    )
    threshold = settings.ocr_min_score if min_score is None else min_score
    lines = [ln for ln in lines if ln.score >= threshold]
    return OcrResponse(
        text="\n".join(ln.text for ln in lines),
        lines=lines,
        width=width,
        height=height,
        deskew_angle=angle,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
