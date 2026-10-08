# Tajik OCR API

![tests](../../actions/workflows/tests.yml/badge.svg)

> **EN:** FastAPI service for Tajik-language OCR (Tesseract `tgk` with full support of ғ ӣ қ ӯ ҳ ҷ)
> and for reading the Tajik national ID card: template alignment, per-field OCR, ICAO 9303 MRZ
> with check digits, and Cyrillic/Latin/MRZ cross-validation of names. Docs below are in Russian.

FastAPI-сервис: отправляешь картинку — получаешь таджикский текст.

Два движка:
- **Tesseract `tgk`** — по умолчанию. Официальная таджикская модель, знает все буквы ғ ӣ қ ӯ ҳ ҷ.
- **PaddleOCR `tg`** — опционально. Общая кириллическая модель: путает ҳ/х, ҷ/ч, ӣ/й, ӯ/у.

Перед распознаванием изображение проходит предобработку: выравнивание освещения (`OCR_FLATTEN`)
и выпрямление наклона (`OCR_DESKEW`).

## Паспорт (ID-карта) Таджикистана — `/passport`

Распознаёт обе стороны ID-карты образца 2017+ (Шиноснома / Identity Card) и возвращает поля в JSON.

| Эндпоинт | |
|---|---|
| `POST /passport` | поля `front` и/или `back` — обе стороны, со сверкой |
| `POST /passport/front` | только лицевая сторона (`file`) |
| `POST /passport/back` | только обратная сторона + MRZ (`file`) |

```powershell
curl.exe -F "front=@front.jpg" -F "back=@back.jpg" http://localhost:8000/passport
```

Как работает:
1. **Выравнивание по шаблону.** Фото сопоставляется с эталоном карты по ключевым точкам SIFT
   (флаг, герб, подписи полей, фоновый узор — у всех карт одинаковые) → гомография → карта
   1024×640. Не зависит от фона, обрезки краёв, поворота (в т.ч. вверх ногами) и перспективы.
   Заодно определяется сторона — неважно, какой файл прислан как `front`, а какой как `back`.
   Эталоны в `app/passport/templates/` обезличены: фото, ФИО, даты, номера, подпись, MRZ стёрты.
   Если сопоставить не удалось — запасной путь через контур карты.
2. **Поля по зонам**: каждое поле читается отдельно своей моделью (`tgk` — кириллица, `eng` —
   латиница/цифры) с проверкой формата; семейное положение и коды стран — по словарю.
3. **MRZ** (`ocrb`) читается в нескольких вариантах, лучший выбирается по 4 контрольным цифрам
   ICAO 9303; строка имён (у неё контрольной цифры нет) — из варианта, где она похожа на имена.
4. **Сверка**:
   - номер документа, даты, пол, гражданство, личный номер — с MRZ;
   - ФИО — голосованием трёх независимых чтений (кириллица, латиница, MRZ) через
     транслитерацию с учётом типичных ошибок OCR: Ч/Ҷ, Х/Ҳ, Л/П, К/Қ, потерянные Ё/Ӯ/Ӣ,
     пропущенная или лишняя буква (ЗУПХАЧОН + ZULHAJON → ЗУЛҲАҶОН);
   - срок действия = дата выдачи + 10 лет − 1 день.

Каждое поле:
```json
"surname_tg": {"value": "ЁРМАТОВ", "raw": "ЕРМАТОВ", "confidence": 0.6, "verified": true,
            "note": "исправлено по латинице (было ЕРМАТОВ)"}
```
`verified`: `true` — подтверждено MRZ/сверкой, `false` — противоречит ей (проверь вручную),
`null` — сверять не с чем. Общие проблемы — в `warnings`.

Поля: `surname_tg/_en`, `name_tg/_en`, `patronymic_tg/_en`, `sex`, `nationality`, `birth_date`,
`birth_place`, `issue_date`, `expiry_date`, `national_id`, `document_number` (лицевая);
`address`, `marital_status`, `blood_group`, `tax_id`, `issuing_authority_tg/_en` (обратная).
Даты — в ISO (`2032-12-15`).

Качество:

| Набор | Все поля | Ключевые поля* |
|---|---|---|
| 3 реальные карты (сканы и фото телефоном; на них же настраивалось) | 57/57 | 39/39 |
| 21 имитация фото из этих карт (наклон до 15°, перспектива, тень, вверх ногами, вертикально, мелко, JPEG q=45) | 94% | 98,5% |

\* ФИО (кир./лат.), пол, гражданство, даты, личный номер, номер документа.
Ни одна ошибка не получила `verified: true` — подтверждённым полям можно доверять, остальные
стоит показать оператору. `sides.*.match_score` < 40 → предупреждение «переснять».
Больше всего ошибок в адресе (длинный свободный текст). ~3,5 с на две стороны.

**Персональные данные.** Сервис ничего не сохраняет и не логирует: изображения живут в памяти только
на время запроса. Для работы в сети: задай `API_KEY` и ставь сервис за HTTPS.
В репозитории нет ни одного реального документа: эталоны в `app/passport/templates/` обезличены,
тесты используют вымышленные имена и образец MRZ из ICAO 9303. Реальные сканы для проверки держи
локально в `samples/` — папка и все `*.jpg` в `.gitignore`. Сканы чужих документов — только с
согласия владельцев.

## Бенчмарк (bench/, 90 синтетических картинок: 5 шрифтов × 6 условий)

| Движок | CER | Таджикские буквы |
|---|---|---|
| **Tesseract tgk + flatten + deskew (через API)** | **0.0%** | **100%** |
| Tesseract tgk без предобработки | 6.0% | 92% |
| EasyOCR tjk | 12.6% | 86% |
| PaddleOCR tg (sample) | — | 33% |

Текст в бенчмарке напечатан компьютером — реальные фото и сканы проверяй отдельно.

```powershell
uv run python bench/make_set.py          # сгенерировать 90 картинок в bench/set
uv run python bench/run_bench.py tesseract --flatten
uv run python bench/run_bench.py paddle  # нужно uv sync --extra paddle
```

## Установка (Windows)

1. **Tesseract**: https://github.com/UB-Mannheim/tesseract/wiki (языки можно не отмечать).
2. **Модели** (`tgk`, `eng` из tessdata_best и `ocrb` для MRZ) — в `models/tessdata/`:
   ```powershell
   uv run python scripts/download_models.py
   ```
   Сервер нужно запускать из папки проекта: путь к моделям передаётся относительным
   (pytesseract не умеет пути с пробелами на Windows).
3. Проект:
   ```powershell
   uv sync                    # только Tesseract (лёгкая установка)
   uv sync --extra paddle     # + PaddleOCR (~1 ГБ), чтобы сравнивать
   copy .env.example .env
   uv run uvicorn app.main:app --port 8000
   ```

Swagger: http://localhost:8000/docs

## API

`POST /ocr` — `multipart/form-data`, поле `file`. Query-параметры (все необязательные):

| Параметр | |
|---|---|
| `engine=tesseract\|paddle` | движок (по умолчанию `OCR_ENGINE`) |
| `flatten=true\|false` | выравнивание освещения |
| `deskew=true\|false` | выпрямление наклона |
| `min_score=0.6` | отбросить неуверенные строки |

```powershell
curl.exe -F "file=@samples/tajik_sample.png" http://localhost:8000/ocr
curl.exe -F "file=@samples/tajik_sample.png" "http://localhost:8000/ocr?engine=paddle"
```

Ответ:
```json
{
  "engine": "tesseract",
  "text": "Ҷумҳурии Тоҷикистон\n...",
  "lines": [{"text": "Ҷумҳурии Тоҷикистон", "score": 0.96, "box": [[43,49],[500,49],[500,86],[43,86]]}],
  "width": 1000, "height": 360,
  "deskew_angle": 0.0,
  "elapsed_ms": 410
}
```
`box` — в координатах выпрямленного изображения (если `deskew_angle` ≠ 0).

`GET /health` — какие движки загружены, версии, для Paddle — `tajik_letters_missing`.

## Разработка

```powershell
uv sync --extra paddle
uv run pytest -q
uvx ruff check app tests scripts
```

## Лицензия

Код — MIT (см. `LICENSE`). Модели Tesseract скачиваются отдельно: `tgk`, `eng` — tessdata_best
(Apache-2.0), `ocrb` — [Shreeshrii/tessdata_ocrb](https://github.com/Shreeshrii/tessdata_ocrb).

## Структура

```
app/config.py            настройки из env/.env
app/preprocess.py        flatten_lighting, deskew
app/engines/tesseract.py Tesseract (pytesseract), группировка слов в строки
app/engines/paddle.py    PaddleOCR
app/main.py              FastAPI: /ocr, /health
app/tess.py              общий вызов Tesseract, поиск моделей
app/passport/align.py    выравнивание по шаблону (SIFT + гомография), определение стороны
app/passport/templates/  обезличенные эталоны сторон карты
app/passport/card.py     запасной поиск карты по контуру
app/passport/layout.py   зоны полей ID-карты
app/passport/reader.py   чтение полей, сверка с MRZ
app/passport/mrz.py      разбор MRZ TD1, контрольные цифры
app/passport/translit.py таджикская транслитерация, исправление ФИО
app/passport/router.py   /passport, /passport/front, /passport/back
tests/                   uv run pytest
bench/                   синтетический бенчмарк движков (make_set.py, run_bench.py)
.github/workflows/       CI: ruff + pytest
scripts/download_models.py
bench/run_bench.py       сравнение движков на bench/set
scripts/make_sample.py   тестовая картинка
```
