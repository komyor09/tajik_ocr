"""FastAPI app: POST an image, get Tajik text back."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.config import get_settings
from app.engines import ENGINES, get_engine, loaded_engines
from app.images import load_upload
from app.passport.router import router as passport_router
from app.preprocess import deskew as deskew_image
from app.preprocess import flatten_lighting
from app.security import require_api_key

log = logging.getLogger("uvicorn.error")
settings = get_settings()

EngineName = Literal["tesseract", "paddle"]


class LineOut(BaseModel):
    text: str
    score: float
    box: list[list[int]]


class OcrResponse(BaseModel):
    engine: str
    text: str
    lines: list[LineOut]
    width: int
    height: int
    deskew_angle: float  # boxes are in the coordinates of the straightened image
    elapsed_ms: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.engine not in ENGINES:
        raise RuntimeError(f"OCR_ENGINE={settings.engine!r}; допустимо: {', '.join(ENGINES)}")
    log.info("Loading default OCR engine: %s", settings.engine)
    engine = await run_in_threadpool(get_engine, settings.engine, settings)
    log.info("Ready: %s", engine.info())
    yield


app = FastAPI(title="Tajik OCR API", version="0.3.0", lifespan=lifespan)
app.include_router(passport_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "default_engine": settings.engine,
        "flatten": settings.flatten,
        "deskew": settings.deskew,
        "engines": {name: e.info() for name, e in loaded_engines().items()},
    }


@app.post("/ocr", response_model=OcrResponse, dependencies=[Depends(require_api_key)])
async def ocr(
    file: UploadFile = File(..., description="Изображение с текстом"),
    engine: EngineName | None = Query(None, description="Движок; по умолчанию OCR_ENGINE"),
    flatten: bool | None = Query(None, description="Выравнивать освещение; по умолчанию OCR_FLATTEN"),
    deskew: bool | None = Query(None, description="Выпрямлять наклонный текст; по умолчанию OCR_DESKEW"),
    min_score: float | None = Query(None, ge=0, le=1, description="Отбросить строки с уверенностью ниже"),
):
    image, width, height = await load_upload(file, settings.max_upload_mb)
    name = engine or settings.engine
    try:
        ocr_engine = await run_in_threadpool(get_engine, name, settings)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    started = time.perf_counter()
    angle = 0.0
    if settings.flatten if flatten is None else flatten:
        image = flatten_lighting(image)
    if settings.deskew if deskew is None else deskew:
        image, angle = deskew_image(image)
    lines = await run_in_threadpool(ocr_engine.recognize, image)
    threshold = settings.min_score if min_score is None else min_score
    lines = [ln for ln in lines if ln.score >= threshold]

    return OcrResponse(
        engine=name,
        text="\n".join(ln.text for ln in lines),
        lines=[LineOut(**ln.__dict__) for ln in lines],
        width=width,
        height=height,
        deskew_angle=angle,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
