# HR API: паспорт → анкета сотрудника

Эндпоинт для автоматизации HR-модуля. Принимает **две стороны ID-карты** гражданина Таджикистана
и возвращает анкету из **18 полей** на нужном языке, с оценкой уверенности для текстовых полей
и списком полей, которые оператору стоит проверить глазами.

```
POST /hr/passport?lang=tg|en
Content-Type: multipart/form-data
X-API-Key: <ключ>        # если в .env задан API_KEY
```

| Параметр | Где | Обязательный | Описание |
|---|---|---|---|
| `front` | файл | да | Лицевая сторона (ФИО, даты, номера) |
| `back` | файл | да | Обратная сторона (адрес, РМА, MRZ) |
| `lang` | query или поле формы | нет | `tg` (по умолчанию) или `en`. Принимаются и `tj`, `tgk`, `tajik`, `eng`, `english` |

Стороны определяются по самим изображениям: если перепутать `front` и `back`, ответ будет тем же
(в `warnings` появится замечание). Форматы: JPG, PNG, WEBP, BMP, TIFF; до `OCR_MAX_UPLOAD_MB` (15 МБ).

## Ответ

`lang=tg`:

```json
{
  "lang": "tg",
  "data": {
    "surname": "Маҳмудова",
    "name": "Гулнора",
    "patronymic": "Абдуқодирзода",
    "gender": "Зан",
    "date_of_birth": "1991-02-22",
    "address": "ВИЛОЯТИ СУҒД, ИСФАРА, ҶАМОАТИ ГУЛИСТОН КӮЧАИ ДӮСТӢ ХОНАИ 54",
    "phone": null,
    "phone_2": null,
    "email": null,
    "marital_status": "Оиладор",
    "nationality": "ТҶК",
    "country": "Тоҷикистон",
    "region": "Суғд",
    "city_or_district": "Исфара",
    "village": "Гулистон",
    "inn": "281948219",
    "national_id": "3518609139099",
    "passport_id": "A60308246"
  },
  "scores": {
    "surname": 0.96, "name": 0.95, "patronymic": 0.95, "address": 0.95,
    "region": 0.95, "city_or_district": 0.95, "village": 0.95, "marital_status": 0.95
  },
  "needs_review": [],
  "warnings": [],
  "elapsed_ms": 3400
}
```

Тот же паспорт с `lang=en`:

```json
{
  "lang": "en",
  "data": {
    "surname": "Mahmudova", "name": "Gulnora", "patronymic": "Abduqodirzoda",
    "gender": "Female", "date_of_birth": "1991-02-22",
    "address": "VILOYATI SUGHD, ISFARA, JAMOATI GULISTON KUCHAI DUSTI KHONAI 54",
    "phone": null, "phone_2": null, "email": null,
    "marital_status": "Married", "nationality": "TJK", "country": "Tajikistan",
    "region": "Sughd", "city_or_district": "Isfara", "village": "Guliston",
    "inn": "281948219", "national_id": "3518609139099", "passport_id": "A60308246"
  },
  "scores": { "...": "как выше" },
  "needs_review": [],
  "warnings": [],
  "elapsed_ms": 3400
}
```

> Данные в примерах вымышленные — это образец, сгенерированный `scripts/make_specimens.py`.

## Поля `data`

| Поле | `tg` | `en` | Источник на карте | `scores` |
|---|---|---|---|---|
| `surname` | Маҳмудова | Mahmudova | Насаб / Surname, MRZ | да |
| `name` | Гулнора | Gulnora | Ном / Name, MRZ | да |
| `patronymic` | Абдуқодирзода | Abduqodirzoda | Номи падар / Father's name | да |
| `gender` | Мард / Зан | Male / Female | Ҷинс / Sex, MRZ | — |
| `date_of_birth` | 1991-02-22 | 1991-02-22 | Санаи таваллуд, MRZ | — |
| `address` | как на карте | транслитерация | Нишонӣ (обратная сторона) | да |
| `phone`, `phone_2`, `email` | `null` | `null` | на карте нет — заполняет HR | — |
| `marital_status` | Муҷаррад / Оиладор / Ҷудошуда / Бева | Single / Married / Divorced / Widowed | Вазъи оилавӣ | да |
| `nationality` | ТҶК | TJK | Шаҳрвандӣ, MRZ | — |
| `country` | Тоҷикистон | Tajikistan | государство выдачи (MRZ) | — |
| `region` | Суғд, Хатлон, ВМКБ, Душанбе… | Sughd, Khatlon… | из адреса | да |
| `city_or_district` | Исфара | Isfara | из адреса | да |
| `village` | Гулистон | Guliston | из адреса (ҷамоат/деҳа), может отсутствовать | да |
| `inn` | 9 цифр | 9 цифр | РМА / Tax Payer ID | — |
| `national_id` | 13 цифр | 13 цифр | Рақами ягонаи миллӣ, MRZ | — |
| `passport_id` | A12345678 | A12345678 | Рақами шиноснома, MRZ | — |

Соглашения:
- ФИО и названия мест — с заглавной буквы (`Маҳмудова`), адрес — как напечатан на карте, без хвоста
  регистрации «№… АЗ <дата> СОЛ».
- Даты — ISO `YYYY-MM-DD`, числа — только цифры; одинаковы для обоих языков.
- В режиме `en` ФИО берутся из латинской строки карты / MRZ; адрес и места — транслитерацией
  таджикского текста (на карте он только на таджикском). Если латиницы нет — тоже транслитерация.
- Поле, которое не удалось прочитать, — `null` (и оно попадёт в `needs_review`).

## `scores` — уверенность для текстовых полей

Оценка 0…1 даётся **только полям с текстом**, где возможна путаница таджикских букв
(ҳ/х, ҷ/ч, қ/к, ғ/г, ӯ/у, ӣ/и, ё/е): `surname`, `name`, `patronymic`, `address`, `region`,
`city_or_district`, `village`, `marital_status`. Для чисел и дат оценки нет: они либо подтверждены
контрольными цифрами MRZ, либо попадают в `needs_review`.

Как считается:
1. База — уверенность Tesseract по словам поля.
2. Подтверждено независимым чтением (кириллица ↔ латиница ↔ MRZ, таджикская и английская части
   семейного положения) — не ниже **0.95**.
3. Противоречит другому чтению — не выше **0.5**.
4. Адрес без распознаваемой структуры (нет «ВИЛОЯТИ …») — не выше 0.5; с обрывками слов — 0.6;
   регион или город не из справочника районов Таджикистана — 0.75.
5. Имя с Ӯ или Ӣ не повышается до 0.95: в латинице `U`/`I` не отличают Ӯ от У и Ӣ от И.

## `needs_review` — что показать оператору

Поле попадает в список, если:
- текстовое поле имеет `score < 0.8`;
- `gender`, `date_of_birth`, `national_id`, `passport_id` не подтверждены MRZ;
- `inn` прочитан с уверенностью < 0.9 (у РМА нет контрольной цифры) или неверной длины;
- обязательное поле пустое (кроме `village`, `phone`, `phone_2`, `email`).

Рекомендуемый UX: подставить `data` в форму, подсветить поля из `needs_review`, остальные
оставить редактируемыми. На тестовых наборах **каждая ошибка распознавания оказалась
в `needs_review`**, а зря помечаются около 2% верных полей на сканах и около 9% на фото
(см. [testing.md](testing.md)).

## `warnings`

Свободный текст для логов и оператора: перепутанные стороны, «низкое качество снимка — переснять»,
непрочитанная строка имён MRZ, несовпадение контрольных цифр и т.п.

## Ошибки

| Код | Когда |
|---|---|
| 400 | неизвестный `lang`, пустой файл |
| 401 | задан `API_KEY`, а `X-API-Key` неверный или отсутствует |
| 413 | файл больше `OCR_MAX_UPLOAD_MB` |
| 415 | файл не является изображением |
| 422 | ни на одном снимке не найдена таджикская ID-карта; не передан `front` или `back` |
| 503 | не установлен Tesseract или нет моделей (`tgk`, `eng`, `ocrb`) |

## Примеры вызова

PowerShell:
```powershell
curl.exe -H "X-API-Key: $env:API_KEY" -F "front=@front.jpg" -F "back=@back.jpg" `
  "http://localhost:8000/hr/passport?lang=tg"
```

Laravel (HTTP-клиент):
```php
use Illuminate\Support\Facades\Http;

$response = Http::withHeaders(['X-API-Key' => config('services.tajik_ocr.key')])
    ->timeout(30)
    ->attach('front', $request->file('front')->get(), 'front.jpg')
    ->attach('back', $request->file('back')->get(), 'back.jpg')
    ->post(config('services.tajik_ocr.url') . '/hr/passport', ['lang' => app()->getLocale() === 'en' ? 'en' : 'tg']);

if ($response->failed()) {
    abort($response->status(), $response->json('detail'));
}

$employee = $response->json('data');          // 18 полей анкеты
$toCheck  = $response->json('needs_review');  // подсветить в форме
```

Python:
```python
import httpx

with open("front.jpg", "rb") as f, open("back.jpg", "rb") as b:
    r = httpx.post(
        "http://localhost:8000/hr/passport",
        params={"lang": "en"},
        files={"front": f, "back": b},
        headers={"X-API-Key": "..."},
        timeout=30,
    )
r.raise_for_status()
print(r.json()["data"], r.json()["needs_review"])
```

## Вспомогательный эндпоинт

`GET /hr/fields` — список полей анкеты, какие из них получают `scores`, какие обязательны,
поддерживаемые языки. Удобно для генерации формы на фронтенде.

## Ограничения

- Только ID-карта образца 2017+ («Шиноснома / Identity Card»). Старый паспорт-книжка не поддерживается.
- Время ответа ~3–4 с на две стороны на обычном CPU.
- Ӯ/Ӣ в ФИО не подтверждаются латиницей — смотри `scores`.
- РМА (ИНН) на фото читается хуже остальных полей и чаще всего уходит в `needs_review`.
- Телефон и e-mail на карте отсутствуют — их заполняет HR.
