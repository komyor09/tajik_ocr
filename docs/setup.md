# Установка, настройка, запуск

## Требования

- Python 3.12–3.13 и [uv](https://docs.astral.sh/uv/)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) 5.x (на Windows — установщик UB Mannheim;
  языки при установке отмечать не обязательно)

## Установка

```powershell
git clone <repo> tajik-ocr
cd tajik-ocr
uv sync                                    # Tesseract-движок (лёгкая установка)
uv sync --extra paddle                     # + PaddleOCR (~1 ГБ) — только для сравнения в /ocr
uv run python scripts/download_models.py   # tgk, eng (tessdata_best) и ocrb (MRZ) → models/tessdata
copy .env.example .env                     # настройки
```

## Запуск

```powershell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Запускайте **из папки проекта**: путь к `models/tessdata` передаётся Tesseract относительным
(pytesseract на Windows не умеет пути с пробелами).

Проверка: `http://localhost:8000/health`, документация — `http://localhost:8000/docs`.

## Настройки (`.env`)

| Переменная | По умолчанию | |
|---|---|---|
| `API_KEY` | — | если задан, нужен заголовок `X-API-Key` на всех эндпоинтах, кроме `/health` |
| `OCR_MAX_UPLOAD_MB` | 15 | максимальный размер файла |
| `OCR_ENGINE` | `tesseract` | движок `/ocr`: `tesseract` или `paddle` |
| `OCR_FLATTEN` | `true` | выравнивание освещения в `/ocr` |
| `OCR_DESKEW` | `true` | выпрямление наклона в `/ocr` |
| `OCR_MIN_SCORE` | 0.0 | порог уверенности строк в `/ocr` |
| `TESSERACT_CMD` | авто | путь к `tesseract.exe`, если его нет в PATH и не в `C:\Program Files\Tesseract-OCR` |
| `TESSERACT_LANG` | `tgk` | язык `/ocr`; `tgk+rus` — для смешанного текста |
| `TESSERACT_PSM` | 3 | разметка страницы в `/ocr`: 3 — авто, 6 — один блок |
| `OCR_LANG`, `OCR_DEVICE`, `OCR_ENABLE_MKLDNN`, `OCR_REC_MODEL_DIR` | | настройки PaddleOCR |

Паспортные эндпоинты (`/passport`, `/hr`) всегда используют Tesseract с моделями `tgk`, `eng`, `ocrb`.

## В продакшене

- Задайте `API_KEY` и ставьте сервис за HTTPS (reverse proxy: nginx, Caddy, IIS).
- Один процесс обрабатывает запросы параллельно (Tesseract запускается отдельными процессами);
  для нагрузки запускайте несколько воркеров: `uvicorn app.main:app --workers 4`.
- Сервис не пишет изображения на диск и не логирует распознанные данные; не включайте
  логирование тел запросов на прокси.
