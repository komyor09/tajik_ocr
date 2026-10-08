"""HR record mapping on fictional data."""

import pytest

from app.hr.mapping import HR_FIELDS, SCORED, build_record, parse_address, score
from app.passport.reader import Field


def F(value, conf=0.9, verified=None):  # noqa: N802
    return Field(value, value or "", conf, verified)


FIELDS = {
    "surname_tg": F("ЁРМАТОВА", 0.9, True),
    "surname_en": F("YORMATOVA", 0.88, True),
    "name_tg": F("ЗУЛҲАҶОН", 0.7, True),
    "name_en": F("ZULHAJON", 0.6, True),
    "patronymic_tg": F("ҚАДАМОВНА", 0.6, False),
    "patronymic_en": F("QADAMOVNA", 0.85),
    "sex": F("F", 1.0, True),
    "nationality": F("TJK", 1.0, True),
    "birth_date": F("1999-03-21", 1.0, True),
    "national_id": F("3500000000001", 1.0, True),
    "document_number": F("A12345678", 1.0, True),
    "address": F("ВИЛОЯТИ ХАТЛОН, ВАХШ, ҶАМОАТИ ГУЛИСТОН КӮЧАИ НАВРӮЗ ХОНАИ 7, №2 АЗ 01.02.2020 СОЛ", 0.86),
    "marital_status": F("ОИЛАДОР/MARRIED", 0.7),
    "tax_id": F("123456789", 0.9),
}


def test_tajik_record():
    r = build_record(FIELDS, "tg", issuer="TJK")
    d = r.data
    assert list(d) == list(HR_FIELDS)
    assert (d["surname"], d["name"], d["patronymic"]) == ("Ёрматова", "Зулҳаҷон", "Қадамовна")
    assert d["gender"] == "Зан"
    assert d["date_of_birth"] == "1999-03-21"
    assert d["address"] == "ВИЛОЯТИ ХАТЛОН, ВАХШ, ҶАМОАТИ ГУЛИСТОН КӮЧАИ НАВРӮЗ ХОНАИ 7"
    assert (d["region"], d["city_or_district"], d["village"]) == ("Хатлон", "Вахш", "Гулистон")
    assert d["marital_status"] == "Оиладор"
    assert (d["nationality"], d["country"]) == ("ТҶК", "Тоҷикистон")
    assert (d["inn"], d["national_id"], d["passport_id"]) == ("123456789", "3500000000001", "A12345678")
    assert d["phone"] is d["phone_2"] is d["email"] is None


def test_english_record():
    d = build_record(FIELDS, "en", issuer="TJK").data
    assert (d["surname"], d["name"], d["patronymic"]) == ("Yormatova", "Zulhajon", "Qadamovna")
    assert d["gender"] == "Female"
    assert (d["region"], d["city_or_district"], d["village"]) == ("Khatlon", "Vakhsh", "Guliston")
    assert d["address"].startswith("VILOYATI KHATLON, VAKHSH")
    assert d["marital_status"] == "Married"
    assert (d["nationality"], d["country"]) == ("TJK", "Tajikistan")


@pytest.mark.parametrize("lang", ["EN", "english", "eng"])
def test_lang_aliases(lang):
    assert build_record(FIELDS, lang).lang == "en"


def test_scores_only_for_text_fields():
    r = build_record(FIELDS, "tg", issuer="TJK")
    assert set(r.scores) == set(SCORED)
    assert "date_of_birth" not in r.scores and "national_id" not in r.scores
    assert r.scores["surname"] == 0.95  # confirmed by cross-check -> at least 0.95
    assert r.scores["patronymic"] == 0.5  # contradicted -> at most 0.5
    assert "patronymic" in r.needs_review and "surname" not in r.needs_review


def test_missing_latin_is_transliterated():
    fields = dict(FIELDS, name_en=F(None, 0.0))
    assert build_record(fields, "en").data["name"] == "Zulhajon"


def test_unconfirmed_numbers_need_review():
    fields = dict(FIELDS, document_number=F("A12345678", 0.9, None))
    assert "passport_id" in build_record(fields, "tg").needs_review


def test_score_missing_is_zero():
    assert score(None) == 0.0 and score(F(None)) == 0.0


@pytest.mark.parametrize(
    "text, region, city, village, full",
    [
        ("ВИЛОЯТИ СУҒД, ХУҶАНД, МАХ 12 БИНОИ 5, НЕЗ АЗ 14.05.2013", "СУҒД", "ХУҶАНД", None,
         "ВИЛОЯТИ СУҒД, ХУҶАНД, МАХ 12 БИНОИ 5"),
        ("ШАҲРИ ДУШАНБЕ, НОҲИЯИ СИНО, КӮЧАИ РӮДАКӢ 10", "ДУШАНБЕ", "СИНО", None,
         "ШАҲРИ ДУШАНБЕ, НОҲИЯИ СИНО, КӮЧАИ РӮДАКӢ 10"),
        ("ВИЛОЯТИ СУҒД, ИСФАРА, ҶАМОАТИ ЧОРКӮҲ М.ТЕСТ, АЗ 01.01.2021 С", "СУҒД", "ИСФАРА", "ЧОРКӮҲ М.ТЕСТ",
         "ВИЛОЯТИ СУҒД, ИСФАРА, ҶАМОАТИ ЧОРКӮҲ М.ТЕСТ"),
    ],
)  # fmt: skip
def test_parse_address(text, region, city, village, full):
    a = parse_address(text)
    assert (a.region, a.city_or_district, a.village, a.full) == (region, city, village, full)


def test_glued_prefixes():
    a = parse_address("ВИЛОЯТИСУҒД, ПАНҶАКЕНТ, МКР 21 БИНОИ 3")
    assert (a.region, a.city_or_district) == ("СУҒД", "ПАНҶАКЕНТ")
    assert parse_address("ШАҲРИДУШАНБЕ, НОҲИЯИСИНО").city_or_district == "СИНО"


def test_address_with_lost_pieces_needs_review():
    fields = dict(FIELDS, address=F("ВИЛОЯТИ ХАТЛОН, БОХТАР, МК ОИ 35", 0.95))
    r = build_record(fields, "tg")
    assert r.scores["address"] <= 0.6 and "address" in r.needs_review


def test_region_word_without_name():
    a = parse_address("ВИЛОЯТИ, АШТ, ҶАМОАТИ НАВБАҲОР")
    assert a.region is None
    assert (
        "address"
        in build_record(dict(FIELDS, address=F("ВИЛОЯТИ, АШТ, ҶАМОАТИ НАВБАҲОР", 0.95)), "en").needs_review
    )


def test_unknown_region_lowers_score():
    r = build_record(dict(FIELDS, address=F("ВИЛОЯТИ БУД, ВАХШ, МКР 2 БИНОИ 4", 0.95)), "tg")
    assert r.scores["region"] <= 0.75 and "region" in r.needs_review
