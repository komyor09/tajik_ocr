from app.passport.reader import MARITAL_EN, MARITAL_TG, _clean_tg, _match_code, _match_code_cyr, _vocab


def test_vocab():
    assert _vocab("МУҶАРРАДМОСЕ", MARITAL_TG) == "МУҶАРРАД"
    assert _vocab("MYYAPPAJLYSINGLE", MARITAL_EN) == "SINGLE"
    assert _vocab("SINGIF", MARITAL_EN) == "SINGLE"


def test_numbers_after_house_words():
    assert _clean_tg("МКР 5 БИНОИ ЗБ") == "МКР 5 БИНОИ 36"
    assert _clean_tg("ДЕҲАИ ОБ") == "ДЕҲАИ ОБ"  # village name, not a number


def test_country_codes():
    assert _match_code("TYKITIK") == "TJK"
    assert _match_code("TUKATIK") == "TJK"
    assert _match_code("TUT") is None  # too far from any code: better empty than wrong
    assert _match_code_cyr("ТЧК/ТЛК") == "TJK"
