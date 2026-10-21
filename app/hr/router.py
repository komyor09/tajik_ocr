"""HR module: both sides of the passport -> the employee registration record (18 fields)."""

import time

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.hr.mapping import HR_FIELDS, LANGS, build_record
from app.images import load_upload
from app.passport.service import CardNotFound, read_passport

router = APIRouter(prefix="/hr", tags=["hr"])
settings = get_settings()


class HrData(BaseModel):
    surname: str | None = Field(None, description="Насаб / Surname")
    name: str | None = Field(None, description="Ном / Name")
    patronymic: str | None = Field(None, description="Номи падар / Father's name")
    gender: str | None = Field(None, description="Мард/Зан или Male/Female")
    date_of_birth: str | None = Field(None, description="YYYY-MM-DD")
    address: str | None = Field(None, description="Нишонӣ, без хвоста регистрации «АЗ <дата>»")
    phone: str | None = Field(None, description="Нет на карте — всегда null")
    phone_2: str | None = Field(None, description="Нет на карте — всегда null")
    email: str | None = Field(None, description="Нет на карте — всегда null")
    marital_status: str | None = Field(None, description="Муҷаррад / Single ...")
    nationality: str | None = Field(None, description="ТҶК или TJK (гражданство)")
    country: str | None = Field(None, description="Тоҷикистон или Tajikistan")
    region: str | None = Field(None, description="Вилоят: Суғд, Хатлон, ВМКБ, Душанбе...")
    city_or_district: str | None = Field(None, description="Шаҳр или ноҳия")
    village: str | None = Field(None, description="Ҷамоат / деҳа")
    inn: str | None = Field(None, description="РМА / ИНН, цифры")
    national_id: str | None = Field(None, description="Рақами ягонаи миллӣ, 13 цифр")
    passport_id: str | None = Field(None, description="Номер ID-карты, напр. A12345678")


class HrResponse(BaseModel):
    lang: str
    data: HrData
    scores: dict[str, float] = Field(description="0..1 только для текстовых полей (таджикские буквы)")
    needs_review: list[str] = Field(description="Поля, которые оператору стоит проверить глазами")
    warnings: list[str]
    elapsed_ms: int


def _lang(query: str | None, form: str | None) -> str:
    lang = (query or form or "tg").strip().lower()
    if lang not in LANGS:
        raise HTTPException(status_code=400, detail="lang: допустимо 'tg' (таджикский) или 'en' (английский)")
    return LANGS[lang]


@router.post(
    "/passport",
    response_model=HrResponse,
    summary="Паспорт → анкета сотрудника (18 полей)",
    responses={
        413: {"description": "Файл больше MAX_UPLOAD_MB"},
        415: {"description": "Не изображение (JPG, PNG, WEBP, BMP, TIFF)"},
        422: {"description": "ID-карта не найдена на изображении"},
    },
)
async def hr_passport(
    front: UploadFile = File(..., description="Лицевая сторона ID-карты"),
    back: UploadFile = File(..., description="Обратная сторона (адрес, РМА, MRZ)"),
    lang: str | None = Query(None, description="tg (по умолчанию) или en"),
    lang_form: str | None = Form(None, alias="lang", description="То же, полем формы"),
):
    language = _lang(lang, lang_form)
    images = [("front", (await load_upload(front, settings.max_upload_mb))[0]),
              ("back", (await load_upload(back, settings.max_upload_mb))[0])]  # fmt: skip
    started = time.perf_counter()
    try:
        r = await run_in_threadpool(read_passport, images)
    except CardNotFound as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:  # Tesseract failed
        raise HTTPException(status_code=503, detail=str(e)) from e

    warnings = list(r.warnings)
    for side in ("front", "back"):
        if side not in r.sides:
            warnings.insert(0, f"нет стороны {side}: часть полей будет пустой")
    record = build_record(r.fields, language, issuer=r.mrz.issuer if r.mrz else None)
    return HrResponse(
        lang=record.lang,
        data=HrData(**record.data),
        scores=record.scores,
        needs_review=record.needs_review,
        warnings=warnings,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@router.get("/fields", summary="Список полей анкеты и какие из них оцениваются")
def hr_fields():
    from app.hr.mapping import REQUIRED, SCORED

    return {
        "fields": list(HR_FIELDS),
        "scored": list(SCORED),
        "required": list(REQUIRED),
        "langs": ["tg", "en"],
    }
