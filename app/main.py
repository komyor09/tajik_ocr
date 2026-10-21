"""Tajik OCR API: text OCR, Tajik ID card reader, HR record. API + Swagger only."""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app import ocr, tess
from app.config import get_settings
from app.hr.router import router as hr_router
from app.passport import align
from app.passport.router import router as passport_router

settings = get_settings()
log = logging.getLogger("tajik_ocr")


def setup_logging(level: str) -> None:
    """All logs (ours and uvicorn's) go to stdout in one format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(level.upper())
    # Docker calls /health every 30 s: keep it out of the access log
    logging.getLogger("uvicorn.access").addFilter(lambda record: "/health" not in record.getMessage())


setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything heavy is done once here, not on each request. Fails fast if models are missing.
    langs = set(tess.PASSPORT_LANGS) | set(settings.tesseract_lang.split("+"))
    version = tess.init(settings.tesseract_cmd, settings.tessdata_dir, langs)
    await run_in_threadpool(align.load_templates)  # SIFT keypoints of the ID card templates
    app.state.tesseract_version = version
    log.info("Ready: tesseract %s, models %s, langs %s", version, settings.tessdata_dir, sorted(langs))
    yield


app = FastAPI(
    title="Tajik OCR API",
    version="0.5.0",
    description="Распознавание таджикского текста и ID-карты Республики Таджикистан. "
    "Изображения не сохраняются и не логируются.",
    lifespan=lifespan,
)
app.include_router(ocr.router)
app.include_router(passport_router)
app.include_router(hr_router)


class HealthResponse(BaseModel):
    status: str
    tesseract: str


@app.get("/health", response_model=HealthResponse, tags=["service"], summary="Проверка работоспособности")
def health():
    return HealthResponse(status="ok", tesseract=app.state.tesseract_version)
