# Деплой через Docker

Образ содержит только движок Tesseract (PaddleOCR не ставится — он тяжёлый и нужен лишь для сравнения).
Модели `tgk`, `eng`, `ocrb` скачиваются при сборке образа, поэтому серверу при `build` нужен доступ к
`raw.githubusercontent.com`, Docker Hub, `deb.debian.org` и PyPI.

## Первый запуск

```bash
git clone https://github.com/komyor09/tajik_ocr.git
cd tajik_ocr
cp .env.example .env
nano .env                      # обязательно задать API_KEY=<длинный случайный ключ>
docker compose up -d --build
docker compose ps              # STATUS должен стать "healthy" через ~20 с
curl http://127.0.0.1:8000/health
```

API слушает только `127.0.0.1:8000`. Наружу его отдаёт reverse proxy с HTTPS (ниже).

## Обновление

```bash
git pull
docker compose up -d --build
docker image prune -f          # удалить старые слои
```

## Настройки

Все переменные из `.env` (см. [setup.md](setup.md)) передаются в контейнер. Дополнительно:

| Переменная | По умолчанию | |
|---|---|---|
| `WEB_CONCURRENCY` | 1 | процессов uvicorn: 1 — для 2 ГБ RAM, 2 — для 4 ГБ и больше |
| `PORT` | 8000 | порт на хосте (только 127.0.0.1) |

`TESSERACT_CMD` в Docker не нужен — Tesseract уже в `PATH`.

## Nginx перед сервисом

```nginx
server {
    server_name ocr.example.tj;
    client_max_body_size 32m;          # /passport принимает две фотографии до OCR_MAX_UPLOAD_MB каждая

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    # HTTPS: sudo certbot --nginx -d ocr.example.tj
}
```

Не включайте логирование тел запросов: в них паспортные данные.

## Логи и диагностика

```bash
docker compose logs -f --tail 100
docker stats tajik-ocr             # CPU / память
```

## Требования к серверу

Замеры на 2 vCPU (образцы из `app/web/static/demo`, фото 2000×1500):

| Запрос | Время ответа | Пропускная способность на 2 vCPU |
|---|---|---|
| `/passport`, `/hr/passport` (2 стороны) | ~4 с | ~20 в минуту |
| `/ocr` (страница текста) | ~0,5 с | ~150 в минуту |

Пиковая память процесса на `/passport` — ~0,8–1 ГБ (вместе с процессами Tesseract).

Для **1000 запросов в день** (в рабочие часы это ~2 запроса в минуту, т. е. запас ×10):

| | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 vCPU | 2–4 vCPU |
| RAM | 2 ГБ (`WEB_CONCURRENCY=1`) | 4 ГБ (`WEB_CONCURRENCY=2`) |
| Диск | 10 ГБ SSD (образ ≈ 0,5 ГБ) | 20 ГБ SSD |
| ОС | Linux x86-64, Docker Engine 24+ с Compose v2.24+ | |
| Сеть | исходящий интернет только на время сборки | |

GPU не нужен. Хранилище данных не нужно: сервис ничего не пишет на диск.
