# Справочник API

Интерактивная документация (Swagger) — `http://localhost:8000/docs`, схема — `/openapi.json`.
Если в `.env` задан `API_KEY`, все эндпоинты, кроме `/health`, требуют заголовок
`X-API-Key`.

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | [`/hr/passport`](hr-api.md) | **Паспорт → анкета сотрудника (18 полей), `lang=tg/en`, scores** |
| `GET` | `/hr/fields` | Поля анкеты, какие оцениваются и обязательны |
| `POST` | `/passport` | Обе стороны ID-карты: все поля + сверка с MRZ (низкоуровневый ответ) |
| `POST` | `/passport/front` | Только лицевая сторона |
| `POST` | `/passport/back` | Только обратная сторона + MRZ |
| `POST` | `/ocr` | Распознать произвольный таджикский текст на изображении |
| `GET` | `/health` | Статус, загруженные движки и модели |
| `GET` | `/`, `/try` | Сайт: лендинг и «API без кода» (tg/uz/ru/en, `?lang=`). Файлы — `app/web/static` |

## `POST /passport`

Поля формы `front` и/или `back` (хотя бы одно). Возвращает каждое поле карты со служебной
информацией — для отладки и для систем, которым нужен полный набор данных.

```json
{
  "fields": {
    "surname_tg": {"value": "МАҲМУДОВА", "raw": "МАҲМУДОВА", "confidence": 0.96, "verified": true, "note": null},
    "document_number": {"value": "A60308246", "raw": "A", "confidence": 0.19, "verified": true,
                        "note": "исправлено по MRZ (было A)"}
  },
  "mrz": {
    "lines": ["IDTJK...", "...", "..."],
    "document_number": "A60308246",
    "checks": {"document_number": true, "birth_date": true, "expiry_date": true, "composite": true},
    "valid": true
  },
  "sides": {
    "front": {"recognized": true, "method": "template", "match_score": 1646, "rotated": false},
    "back": {"recognized": true, "method": "template", "match_score": 405, "rotated": false}
  },
  "warnings": [],
  "elapsed_ms": 3200
}
```

Поле:
- `value` — итоговое значение (после исправлений), `raw` — что прочитал OCR;
- `confidence` — уверенность Tesseract 0…1;
- `verified`: `true` — подтверждено MRZ/сверкой, `false` — противоречит, `null` — сверять не с чем;
- `note` — что было исправлено и почему.

Поля лицевой стороны: `surname_tg/_en`, `name_tg/_en`, `patronymic_tg/_en`, `sex`, `nationality`,
`birth_date`, `birth_place`, `issue_date`, `expiry_date`, `national_id`, `document_number`.
Обратной: `address`, `marital_status`, `blood_group`, `tax_id`, `issuing_authority_tg/_en`.

`sides.*.match_score` — сколько ключевых точек совпало с эталоном карты; меньше 40 означает
плохой снимок (в `warnings` будет просьба переснять).

## `POST /ocr`

Произвольный текст на таджикском (вывески, документы, скриншоты).

| Параметр | Описание |
|---|---|
| `file` | изображение |
| `engine=tesseract\|paddle` | движок (по умолчанию `OCR_ENGINE`) |
| `flatten=true\|false` | выравнивание освещения |
| `deskew=true\|false` | выпрямление наклона |
| `min_score=0.6` | отбросить строки с уверенностью ниже |

```json
{
  "engine": "tesseract",
  "text": "Ҷумҳурии Тоҷикистон\n...",
  "lines": [{"text": "Ҷумҳурии Тоҷикистон", "score": 0.96, "box": [[43,49],[500,49],[500,86],[43,86]]}],
  "width": 1000, "height": 360, "deskew_angle": 0.0, "elapsed_ms": 410
}
```

`box` — в координатах выпрямленного изображения (если `deskew_angle` ≠ 0).

## Коды ошибок

`400` неверный параметр или пустой файл · `401` неверный `X-API-Key` · `413` файл слишком большой ·
`415` не изображение · `422` ID-карта не найдена · `503` нет Tesseract или моделей.
Тело ошибки: `{"detail": "текст на русском"}`.
