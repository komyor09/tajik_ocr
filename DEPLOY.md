# Деплой: Tajik OCR API (внутренний сервис)

Только API и Swagger. Движок — Tesseract 5 (CPU), модели `tgk`, `eng`, `ocrb` лежат в volume `/models`
и в образ не входят. Изображения не сохраняются и не логируются.

## 1. Модели

Нужны три файла (~31 МБ) в одной папке на сервере, например `/srv/models/tessdata`:

```bash
# из клона репозитория, на сервере с доступом к GitHub
python3 scripts/download_models.py /srv/models/tessdata
# или скопировать с машины разработчика
scp models/tessdata/*.traineddata user@server:/srv/models/tessdata/
```

Результат: `/srv/models/tessdata/{tgk,eng,ocrb}.traineddata`. Если чего-то нет, контейнер не стартует
и пишет в лог, какой модели не хватает.

## 2. Сборка и запуск

```bash
cp .env.example .env              # при необходимости поправить
docker build -t tajik-ocr .
docker run -d --name tajik-ocr -p 8000:8000 \
  -v /srv/models:/models:ro --env-file .env tajik-ocr
docker logs -f tajik-ocr          # "Ready: tesseract 5.x, models /models/tessdata ..."
docker inspect --format '{{.State.Health.Status}}' tajik-ocr   # healthy через ~30 с
```

Для локальной проверки без nginx уберите префикс: `-e UVICORN_ROOT_PATH=` (тогда Swagger на
`http://localhost:8000/docs`).

## 3. Переменные окружения

| Переменная | По умолчанию | |
|---|---|---|
| `LOG_LEVEL` | `INFO` | уровень логов (stdout) |
| `MAX_UPLOAD_MB` | `10` | размер одного файла, больше → `413` |
| `TESSDATA_DIR` | `/models/tessdata` (в образе) | папка с `.traineddata` |
| `TESSERACT_LANG` | `tgk` | язык `/ocr`; `tgk+rus` — нужен ещё `rus.traineddata` |
| `TESSERACT_PSM` | `3` | разметка страницы `/ocr`: 3 — авто, 6 — один блок |
| `OCR_THREADS` | `2` | параллельных процессов Tesseract на один паспорт (= ядра CPU) |
| `OCR_FLATTEN`, `OCR_DESKEW`, `OCR_MIN_SCORE` | `true`, `true`, `0.0` | умолчания `/ocr` |
| `TESSERACT_CMD` | — | путь к бинарнику, если его нет в PATH (в Docker не нужен) |
| `UVICORN_ROOT_PATH` | — | префикс за nginx: `/ocr` → Swagger на `/ocr/docs` |

## 4. Эндпоинты

| Метод | Путь | |
|---|---|---|
| `POST` | `/ocr` | таджикский текст с изображения |
| `POST` | `/passport` | ID-карта, обе стороны (`front`, `back`): поля + сверка с MRZ |
| `POST` | `/passport/front`, `/passport/back` | одна сторона (`file`) |
| `POST` | `/hr/passport` | обе стороны → анкета сотрудника из 18 полей, `?lang=tg\|en` |
| `GET` | `/hr/fields` | список полей анкеты |
| `GET` | `/health` | healthcheck |
| `GET` | `/docs`, `/openapi.json` | Swagger |

Форматы: JPG, PNG, WEBP, BMP, TIFF (проверяется по содержимому файла). Ошибки: `400` пустой файл,
`413` больше `MAX_UPLOAD_MB`, `415` не изображение, `422` ID-карта не найдена, `503` сбой Tesseract.

```bash
B=http://localhost:8000            # через nginx: http://<сервер>/ocr
curl $B/health
curl -F "file=@text.jpg" "$B/ocr?min_score=0.5"
curl -F "front=@front.jpg" -F "back=@back.jpg" $B/passport
curl -F "front=@front.jpg" -F "back=@back.jpg" "$B/hr/passport?lang=en"
```

Подробно о полях: [docs/hr-api.md](docs/hr-api.md), [docs/api.md](docs/api.md).

## 5. nginx (для общего конфига)

Префикс **срезается** nginx (слеш в конце `proxy_pass`), а `UVICORN_ROOT_PATH=/ocr` сообщает
приложению, где оно опубликовано: так работают и эндпоинты, и Swagger.

```nginx
location /ocr/ {
    proxy_pass http://tajik-ocr:8000/;      # слеш в конце: /ocr/hr/passport -> /hr/passport
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 21m;               # две фотографии по MAX_UPLOAD_MB
    proxy_read_timeout 60s;
    limit_conn ocr_conn 2;                  # не больше 2 одновременных запросов: память
}
```

## 6. Ресурсы

Замеры на 2 vCPU: `/passport` ~3,5 с, `/ocr` ~0,5 с. Память: ~250 МБ после старта, ~450 МБ после
первых запросов, пик ~0,7 ГБ при двух паспортах одновременно (вместе с процессами Tesseract).
Рекомендуемое в compose: `mem_limit: 1g` и `tmpfs: [/tmp]` — FastAPI временно держит загрузки
больше 1 МБ в `/tmp`, с tmpfs паспортные фото не касаются диска. Для `limit_conn` в блоке `http` нужна зона:
`limit_conn_zone $server_name zone=ocr_conn:1m;`.

## 7. Тесты

```bash
uv sync && uv run pytest -q        # без Tesseract и моделей: проверки MRZ, транслита, загрузки
```
