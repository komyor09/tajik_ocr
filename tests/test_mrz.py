from datetime import date

from app.passport.mrz import check_digit, clean_lines, parse

# Specimen from ICAO Doc 9303 part 5 (TD1)
ICAO = ["I<UTOD231458907<<<<<<<<<<<<<<<", "7408122F1204159UTO<<<<<<<<<<<6", "ERIKSSON<<ANNA<MARIA<<<<<<<<<<"]


def test_check_digit():
    assert check_digit("D23145890") == "7"
    assert check_digit("740812") == "2"
    assert check_digit("120415") == "9"


def test_parse_icao_specimen():
    m = parse(ICAO)
    assert m.valid
    assert m.document_number == "D23145890"
    assert m.birth_date == date(1974, 8, 12)
    assert m.expiry_date == date(2012, 4, 15)
    assert m.sex == "F"
    assert (m.surname, m.given_names) == ("ERIKSSON", "ANNA MARIA")


def test_ocr_noise_is_repaired():
    noisy = "I<UTOD23I458907<<<<<<<<<<<<<<<\n74O8122F12O4159UT0<<<<<<<<<<<6\nERIKSSON<<ANNA<MARIA<<<<<<<<"
    m = parse(clean_lines(noisy))
    assert m.valid
    assert m.document_number == "D23145890"


def test_clean_lines_rejects_plain_text():
    assert clean_lines("Republic of Tajikistan\nИдентификатсия") is None


def test_tajik_document_number_format():
    from app.passport.mrz import check_digit as cd

    doc = "AZ3218621"  # passes its checksum but is not letter + 8 digits
    l1 = f"IDTJK{doc}{cd(doc)}3500000000001".ljust(30, "<")
    l2 = "0412122M2802264TJK".ljust(29, "<")
    l2 += cd(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29])
    m = parse([l1, l2, "TESTOV<<TEST".ljust(30, "<")])
    assert m.checks["document_number"] is False
