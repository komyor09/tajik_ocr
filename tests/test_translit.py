import pytest

from app.passport.translit import fix_words, matches, repair, to_latin


@pytest.mark.parametrize(
    "cyr, lat",
    [
        ("ҲОҶИЕВА", "HOJIEVA"),
        ("ҒОЗИЕВ", "GHOZIEV"),
        ("ХУСРАВ", "KHUSRAV"),
        ("ЁРОВ", "YOROV"),
        ("ҚУРБОНОВ", "QURBONOV"),
    ],
)
def test_matches(cyr, lat):
    assert matches(cyr, lat)


@pytest.mark.parametrize(
    "ocr, lat, expected",
    [
        ("ЕРМАТОВ", "YORMATOV", "ЁРМАТОВ"),  # lost dots over Ё
        ("РАҲИМЧОНОВ", "RAHIMJONOV", "РАҲИМҶОНОВ"),  # Ҷ read as Ч
        ("EPMATOB", "YORMATOV", "ЁРМАТОВ"),  # Cyrillic read as Latin look-alikes
        ("АРАМОВ", "AKRAMOV", "АКРАМОВ"),  # dropped letter: K -> К, not Қ
        ("ДСТМУРОД", "DUSTMUROD", "ДӮСТМУРОД"),  # dropped Ӯ
        ("ЗУПХАЧОН", "ZULHAJON", "ЗУЛҲАҶОН"),  # Л/П, Ҳ/Х, Ҷ/Ч; single H is Ҳ
        ("КАЛАМОВ", "QADAMOV", "ҚАДАМОВ"),  # К/Қ, Л/Д
    ],
)
def test_repair(ocr, lat, expected):
    assert repair(ocr, lat)[0] == expected


def test_kh_is_x():
    assert repair("ХУСРАВ", "KHUSRAV") == ("ХУСРАВ", 0)
    assert to_latin("ЗУЛҲАҶОН") == "ZULHAJON"


def test_repair_gives_up_on_different_names():
    assert repair("ИВАНОВ", "PETROV") is None


def test_fix_words():
    assert fix_words("ДАР НОХИЯИ ВАХШ") == "ДАР НОҲИЯИ ВАХШ"
    assert fix_words("ВИЛОЯТИ СУГД") == "ВИЛОЯТИ СУҒД"
