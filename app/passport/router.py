"""Tajik ID card (passport) recognition endpoints."""

import time
from dataclasses import asdict

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.images import load_upload
from app.passport import reader
from app.passport.service import CardNotFound, read_passport

# Personal data: nothing is logged or stored, images live only in memory for the request
ERRORS = {
    413: {"description": "Файл больше MAX_UPLOAD_MB"},
    415: {"description": "Не изображение (JPG, PNG, WEBP, BMP, TIFF)"},
    422: {"description": "ID-карта не найдена на изображении"},
}
router = APIRouter(prefix="/passport", tags=["passport"], responses=ERRORS)
settings = get_settings()


class FieldOut(BaseModel):
    value: str | None = Field(description="Итоговое значение (после сверки с MRZ)")
    raw: str = Field(description="Что прочитал OCR")
    confidence: float = Field(description="Уверенность 0..1")
    verified: bool | None = Field(None, description="true — подтверждено MRZ, false — противоречит MRZ")
    note: str | None = None


class SideInfo(BaseModel):
    recognized: bool
    method: str = Field(description="template (по шаблону карты) | contour (запасной) | none")
    match_score: int = Field(description="Совпавшие точки с шаблоном; < 60 — плохое фото")
    rotated: bool = Field(description="Карта была перевёрнута")


class PassportResponse(BaseModel):
    fields: dict[str, FieldOut] = Field(description="Поля карты: surname, name, date_of_birth, ...")
    mrz: dict | None = Field(description="Разобранная MRZ с обратной стороны")
    sides: dict[str, SideInfo]
    warnings: list[str]
    elapsed_ms: int


def _side_info(s: reader.SideResult) -> SideInfo:
    return SideInfo(recognized=s.recognized, method=s.method, match_score=s.match_score, rotated=s.rotated)


def _process(images: list[tuple[str, object]]) -> dict:
    try:
        r = read_passport(images)
    except CardNotFound as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    back = r.sides.get("back")
    return {
        "fields": {k: asdict(v) for k, v in r.fields.items()},
        "mrz": reader.mrz_dict(back.mrz) if back else None,
        "sides": {k: _side_info(v) for k, v in r.sides.items()},
        "warnings": r.warnings,
    }


async def _run(uploads: dict[str, UploadFile | None]) -> dict:
    images = [(name, (await load_upload(f, settings.max_upload_mb))[0]) for name, f in uploads.items() if f]
    started = time.perf_counter()
    try:
        result = await run_in_threadpool(_process, images)
    except RuntimeError as e:  # Tesseract failed
        raise HTTPException(status_code=503, detail=str(e)) from e
    result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return result


@router.post("", response_model=PassportResponse, summary="Обе стороны: поля + сверка с MRZ")
async def passport(
    front: UploadFile | None = File(None, description="Лицевая сторона"),
    back: UploadFile | None = File(None, description="Обратная сторона (с MRZ)"),
):
    if front is None and back is None:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один файл: front или back")
    return await _run({"front": front, "back": back})


@router.post("/front", response_model=PassportResponse, summary="Лицевая сторона")
async def passport_front(file: UploadFile = File(...)):
    return await _run({"file": file})


@router.post("/back", response_model=PassportResponse, summary="Обратная сторона + MRZ")
async def passport_back(file: UploadFile = File(...)):
    return await _run({"file": file})
