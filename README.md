# Tajik OCR API

![tests](../../actions/workflows/tests.yml/badge.svg)

> **EN:** FastAPI service for Tajik-language OCR and for reading the Tajik national ID card.
> `POST /hr/passport` turns both sides of the card into an 18-field employee record in Tajik or
> English, with confidence scores for text fields and a list of fields for human review.
> Tesseract `tgk` (full ғ ӣ қ ӯ ҳ ҷ support), SIFT template alignment, ICAO 9303 MRZ check digits,
> Cyrillic/Latin/MRZ name voting. Runs fully locally. Docs are in Russian.

Сервис распознавания таджикского текста и ID-карты гражданина Таджикистана. Всё работает
локально: ни изображения, ни данные никуда не отправляются.

## Что умеет

| Эндпоинт | Для чего |
|---|---|
| **`POST /hr/passport`** | **Две стороны ID-карты → анкета сотрудника из 18 полей на `tg` или `en`, с `scores` и `needs_review`.** Для HR-модуля. → [docs/hr-api.md](docs/hr-api.md) |
| `POST /passport` | Все поля карты с исходным чтением OCR, уверенностью, сверкой с MRZ и пояснениями |
| `POST /ocr` | Любой таджикский текст на изображении (Tesseract `tgk`, опционально PaddleOCR) |
| `GET /` · `GET /try` | Лендинг и страница «API без кода»: загрузка фото, результат таблицей, экспорт JSON/CSV, готовый код. 4 языка: тоҷикӣ, oʻzbekcha, русский, English |

```powershell
curl.exe -F "front=@front.jpg" -F "back=@back.jpg" "http://localhost:8000/hr/passport?lang=tg"
```

```json
{
  "lang": "tg",
  "data": {
    "surname": "Маҳмудова", "name": "Гулнора", "patronymic": "Абдуқодирзода",
    "gender": "Зан", "date_of_birth": "1991-02-22",
    "address": "ВИЛОЯТИ СУҒД, ИСФАРА, ҶАМОАТИ ГУЛИСТОН КӮЧАИ ДӮСТӢ ХОНАИ 54",
    "phone": null, "phone_2": null, "email": null,
    "marital_status": "Оиладор", "nationality": "ТҶК", "country": "Тоҷикистон",
    "region": "Суғд", "city_or_district": "Исфара", "village": "Гулистон",
    "inn": "281948219", "national_id": "3518609139099", "passport_id": "A60308246"
  },
  "scores": {"surname": 0.96, "name": 0.95, "patronymic": 0.95, "address": 0.95, "...": "..."},
  "needs_review": [],
  "warnings": [],
  "elapsed_ms": 3400
}
```

<sub>Данные вымышленные — образец из `scripts/make_specimens.py`.</sub>

## Как это работает — коротко

1. Фото совмещается с обезличенным эталоном карты по ключевым точкам (SIFT + гомография):
   неважны фон, обрезка, поворот, перспектива и какой файл прислан как `front`/`back`.
2. Каждое поле читается отдельно своей моделью Tesseract (`tgk` — кириллица, `eng` — латиница,
   `ocrb` — MRZ).
3. Значения сверяются между собой: MRZ с контрольными цифрами, ФИО — голосованием кириллицы,
   латиницы и MRZ через таджикскую транслитерацию, адрес — со справочником районов.
4. Подтверждённые поля получают высокую оценку, сомнительные попадают в `needs_review`.

Подробно — [docs/architecture.md](docs/architecture.md).

## Качество

Вымышленные образцы, `/hr/passport` (подробности — [docs/testing.md](docs/testing.md)):

| Набор | Верно (`tg` / `en`) | Ошибок без пометки `needs_review` |
|---|---|---|
| 20 «сканов» | 100% / 100% | 0 |
| 30 «фото телефоном» (не использовались при настройке) | 90,8% / 92,2% | 0 |

ФИО, пол, даты, личный номер и номер документа на «фото» — 28–30 из 30. Слабые места:
РМА/ИНН и части адреса — они честно уходят в `needs_review`.

## Быстрый старт (Windows)

1. Установите [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) и [uv](https://docs.astral.sh/uv/).
2. В папке проекта:
   ```powershell
   uv sync
   uv run python scripts/download_models.py
   copy .env.example .env
   uv run uvicorn app.main:app --port 8000
   ```
3. Откройте `http://localhost:8000` (сайт), `http://localhost:8000/try` (проверка без кода)
   или `http://localhost:8000/docs` (Swagger).

Настройки, продакшен, API-ключ — [docs/setup.md](docs/setup.md).

## Документация

| | |
|---|---|
| [docs/hr-api.md](docs/hr-api.md) | HR API: поля, языки, `scores`, `needs_review`, примеры для Laravel/Python |
| [docs/api.md](docs/api.md) | Справочник всех эндпоинтов и ошибок |
| [docs/architecture.md](docs/architecture.md) | Конвейер, модули, решения и ограничения |
| [docs/setup.md](docs/setup.md) | Установка, настройки `.env`, запуск в продакшене |
| [docs/testing.md](docs/testing.md) | Тесты, генератор образцов, оценка качества, бенчмарк |
| [docs/privacy.md](docs/privacy.md) | Персональные данные: правила сервиса и репозитория |

## Разработка

```powershell
uv sync --extra paddle
uv run pytest -q
uvx ruff check app tests scripts
uv run python scripts/make_specimens.py -n 30 --photo && uv run python scripts/eval_specimens.py
```

## Ограничения

- Только ID-карта образца 2017+ («Шиноснома / Identity Card»); старый паспорт-книжка не поддерживается.
- ~3–4 с на две стороны на обычном CPU.
- Реальных карт в оценке пока мало (3): для продакшена нужна проверка на 20–30 картах с согласия владельцев.

## Лицензия

Код — MIT ([LICENSE](LICENSE)). Модели Tesseract скачиваются отдельно: `tgk`, `eng` —
[tessdata_best](https://github.com/tesseract-ocr/tessdata_best) (Apache-2.0), `ocrb` —
[Shreeshrii/tessdata_ocrb](https://github.com/Shreeshrii/tessdata_ocrb).
