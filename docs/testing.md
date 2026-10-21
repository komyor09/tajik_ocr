# Тестирование

## Юнит-тесты

```powershell
uv run pytest -q
```

Тесты не требуют Tesseract, моделей и изображений: разбор MRZ (образец из ICAO 9303),
транслитерация и исправление ФИО, словарь адресов, маппинг анкеты HR, проверки загрузки
(`400`/`413`/`415`) и Swagger. Запускаются в GitHub Actions при каждом пуше.

## Проверка сервиса

После запуска (см. [DEPLOY.md](../DEPLOY.md)):

```bash
curl http://localhost:8000/health
curl -F "front=@front.jpg" -F "back=@back.jpg" "http://localhost:8000/hr/passport?lang=en"
```

## Оценка качества

Генератор вымышленных образцов карт (`scripts/make_specimens.py`, `scripts/eval_specimens.py`)
и бенчмарк `/ocr` (`bench/`) остались в ветке `main` — во внутренний сервис они не входят.
Результаты замеров там же, в `docs/testing.md`.
