"""Passport fields -> the HR registration record (18 fields), in Tajik or English.

Rules
-----
* `lang="tg"`: Tajik (Cyrillic) values as printed on the card; `lang="en"`: Latin values
  (names from the Latin line / MRZ, addresses transliterated).
* Names and place names are returned in Title Case ("Ёрматов"), the full address as printed.
* Dates are ISO (YYYY-MM-DD), numbers are digits only — the same in both languages.
* `scores` are given only for text fields (where Tajik letters can be misread). Numbers and
  dates have none: they are either confirmed by MRZ check digits or listed in `needs_review`.
"""

import re
from dataclasses import dataclass, field

from app.passport.reader import Field
from app.passport.translit import PLACES, to_latin

LANGS = {
    "tg": "tg", "tj": "tg", "tgk": "tg", "taj": "tg", "tajik": "tg", "тоҷикӣ": "tg",
    "en": "en", "eng": "en", "english": "en", "latin": "en",
}  # fmt: skip

HR_FIELDS = (
    "surname", "name", "patronymic", "gender", "date_of_birth", "address",
    "phone", "phone_2", "email", "marital_status", "nationality", "country",
    "region", "city_or_district", "village", "inn", "national_id", "passport_id",
)  # fmt: skip

# Fields that get a score: free text that may contain Tajik letters
SCORED = (
    "surname",
    "name",
    "patronymic",
    "address",
    "region",
    "city_or_district",
    "village",
    "marital_status",
)
# Fields HR cannot do without: missing or unconfirmed -> needs_review
REQUIRED = ("surname", "name", "gender", "date_of_birth", "national_id", "passport_id")
# Present on every card: empty -> needs_review (village/phone/email may legitimately be absent)
EXPECTED = ("surname", "name", "patronymic", "gender", "date_of_birth", "address", "marital_status",
            "nationality", "country", "region", "city_or_district", "inn",
            "national_id", "passport_id")  # fmt: skip
REVIEW_BELOW = 0.8

GENDER = {"M": {"tg": "Мард", "en": "Male"}, "F": {"tg": "Зан", "en": "Female"}}
MARITAL = {"МУҶАРРАД": "SINGLE", "ОИЛАДОР": "MARRIED", "ЗАНДОР": "MARRIED", "ШАВҲАРДОР": "MARRIED",
           "ҶУДОШУДА": "DIVORCED", "БЕВА": "WIDOWED", "ЗАНМУРДА": "WIDOWED"}  # fmt: skip
MARITAL_EN = {"SINGLE": "МУҶАРРАД", "MARRIED": "ОИЛАДОР", "DIVORCED": "ҶУДОШУДА", "WIDOWED": "БЕВА",
              "WIDOW": "БЕВА", "WIDOWER": "ЗАНМУРДА"}  # fmt: skip
COUNTRIES = {
    "TJK": {"code_tg": "ТҶК", "tg": "Тоҷикистон", "en": "Tajikistan"},
    "RUS": {"code_tg": "РУС", "tg": "Русия", "en": "Russia"},
    "UZB": {"code_tg": "ӮЗБ", "tg": "Ӯзбекистон", "en": "Uzbekistan"},
    "KGZ": {"code_tg": "ҚИР", "tg": "Қирғизистон", "en": "Kyrgyzstan"},
    "KAZ": {"code_tg": "ҚАЗ", "tg": "Қазоқистон", "en": "Kazakhstan"},
    "AFG": {"code_tg": "АФҒ", "tg": "Афғонистон", "en": "Afghanistan"},
}

# --------------------------------------------------------------------------- address

# Registration tail: ", №3 АЗ 14.05.2013 СОЛ" ("№" is often misread, e.g. "НЕЗ")
_REGISTRATION = re.compile(
    r"(?:,\s*(?:№\s*)?\S{1,4}\s+|[,\s]+)АЗ\s+\d{2}\.\d{2}\.\d{4}\s*(?:СОЛИ|СОЛ|С)?\.?\s*$"
)
_REGION_PREFIX = re.compile(r"^(?:ВИЛОЯТИ|ВИЛОЯТ)\s*")  # OCR may glue the words
_CITY_PREFIX = re.compile(r"^(?:НОҲИЯИ|ШАҲРИ)\s*|^(?:НОҲИЯ|ШАҲР)\s+")
_VILLAGE = re.compile(r"(?:ҶАМОАТИ|ДЕҲАИ|ҚИШЛОҚИ)\s+(.+?)(?=\s+(?:КӮЧАИ|КУЧАИ|ХОНАИ|БИНОИ|МАХ|МКР|КВ)\b|$)")
_REGION_ALIASES = {"ВМКБ": "ВМКБ", "НТМ": "НТМ", "ДУШАНБЕ": "ДУШАНБЕ"}


_SHORT_OK = {"АЗ", "КВ", "С", "М", "Б", "МКР"}


def _fragments(text: str) -> bool:
    """1-2 letter Cyrillic tokens that are not known abbreviations = OCR lost part of a word."""
    return any(len(t) <= 2 and t not in _SHORT_OK for t in re.findall(r"[А-ЯЁҒӢҚӮҲҶ]+", text))


@dataclass
class Address:
    full: str | None = None
    region: str | None = None
    city_or_district: str | None = None
    village: str | None = None


def parse_address(text: str | None) -> Address:
    """'ВИЛОЯТИ СУҒД, ХУҶАНД, МАХ 12 БИНОИ 5, №2 АЗ 01.02.2020' ->
    region СУҒД, city ХУҶАНД, full address without the registration tail ('№2 АЗ <date>')."""
    if not text:
        return Address()
    full = _REGISTRATION.sub("", text.strip()).strip(" ,")
    parts = [p.strip() for p in full.split(",") if p.strip()]
    a = Address(full=full or None)
    rest: list[str] = []
    for p in parts:
        if a.region is None and (
            _REGION_PREFIX.match(p) or p in _REGION_ALIASES or p.replace(" ", "") == "ШАҲРИДУШАНБЕ"
        ):
            a.region = _CITY_PREFIX.sub("", _REGION_PREFIX.sub("", p)) or None  # bare "ВИЛОЯТИ"
        elif (
            a.region is not None
            and a.city_or_district is None
            and not _VILLAGE.match(p)
            and not re.search(r"\d", p)
        ):
            a.city_or_district = _CITY_PREFIX.sub("", p)
        else:
            rest.append(p)
    if a.region == "ДУШАНБЕ" and a.city_or_district is None:
        a.city_or_district = "ДУШАНБЕ"
    m = _VILLAGE.search(" ".join(rest))
    if m:
        a.village = m.group(1).strip(" ,.")
    return a


# --------------------------------------------------------------------------- scoring


def score(f: Field | None) -> float:
    """OCR confidence adjusted by cross-checks: confirmed by MRZ/transliteration -> at least 0.95,
    contradicted -> at most 0.5, missing -> 0."""
    if f is None or f.value is None:
        return 0.0
    s = f.confidence
    if f.verified is True:
        s = max(s, 0.95)
    elif f.verified is False:
        s = min(s, 0.5)
    return round(s, 2)


# --------------------------------------------------------------------------- record


@dataclass
class HrRecord:
    lang: str
    data: dict[str, str | None]
    scores: dict[str, float]
    needs_review: list[str] = field(default_factory=list)


def _title(s: str | None) -> str | None:
    return s.title() if s else None


def _value(f: Field | None) -> str | None:
    return f.value if f else None


def build_record(fields: dict[str, Field], lang: str, issuer: str | None = None) -> HrRecord:
    lang = LANGS[lang.lower()]
    tg = lang == "tg"
    g = fields.get
    data: dict[str, str | None] = dict.fromkeys(HR_FIELDS)
    scores: dict[str, float] = {}

    # names: Cyrillic or Latin reading of the card
    for hr_key, key in (("surname", "surname"), ("name", "name"), ("patronymic", "patronymic")):
        src = g(f"{key}_tg") if tg else g(f"{key}_en")
        if not tg and _value(src) is None and _value(g(f"{key}_tg")):  # no Latin: transliterate
            src = Field(to_latin(g(f"{key}_tg").value), "", g(f"{key}_tg").confidence, None)
        data[hr_key] = _title(_value(src))
        scores[hr_key] = score(src)

    sex = _value(g("sex"))
    data["gender"] = GENDER[sex][lang] if sex in GENDER else None
    data["date_of_birth"] = _value(g("birth_date"))

    # address and its parts (only on the back, only in Tajik on the card)
    addr_f = g("address")
    addr = parse_address(_value(addr_f))
    conv = (lambda s: s) if tg else (lambda s: to_latin(s) if s else None)
    data["address"] = conv(addr.full)
    data["region"] = _title(conv(addr.region))
    data["city_or_district"] = _title(conv(addr.city_or_district))
    data["village"] = _title(conv(addr.village))
    addr_score = score(addr_f)
    if addr.full and addr.region is None:  # no recognisable structure: probably misread
        addr_score = min(addr_score, 0.5)
    elif any(
        part and not all(w in PLACES for w in part.split()) for part in (addr.region, addr.city_or_district)
    ):
        addr_score = min(addr_score, 0.75)  # unknown place name: may be misread
    if addr.full and _fragments(addr.full):  # "МК ОИ 35": pieces of lost words
        addr_score = min(addr_score, 0.6)
    for k in ("address", "region", "city_or_district", "village"):
        scores[k] = addr_score if data[k] else 0.0

    # marital status: "МУҶАРРАД/SINGLE"
    ms_f = g("marital_status")
    ms_tg, ms_en = None, None
    if ms_f and ms_f.value:
        parts = ms_f.value.split("/")
        ms_tg = next((p for p in parts if re.search(r"[А-ЯЁҒӢҚӮҲҶ]", p)), None)
        ms_en = next((p for p in parts if re.fullmatch(r"[A-Z ]+", p)), None)
        ms_en = ms_en or MARITAL.get(ms_tg or "")
        ms_tg = ms_tg or MARITAL_EN.get(ms_en or "")
    ms = ms_tg if tg else ms_en
    data["marital_status"] = _title(ms)
    scores["marital_status"] = score(ms_f) if ms else 0.0

    # citizenship and country
    nat = _value(g("nationality"))
    country = issuer or nat
    data["nationality"] = (COUNTRIES[nat]["code_tg"] if tg else nat) if nat in COUNTRIES else nat
    data["country"] = COUNTRIES[country][lang] if country in COUNTRIES else country

    # numbers: digits only, language-independent
    data["inn"] = _value(g("tax_id"))
    data["national_id"] = _value(g("national_id"))
    data["passport_id"] = _value(g("document_number"))

    review = [k for k in SCORED if data[k] is not None and scores[k] < REVIEW_BELOW]
    for k, src in (("gender", "sex"), ("date_of_birth", "birth_date"), ("national_id", "national_id"),
                   ("passport_id", "document_number")):  # fmt: skip
        if data[k] is not None and g(src) is not None and g(src).verified is not True:
            review.append(k)
    inn = g("tax_id")  # no check digit: trust only a confident read
    if data["inn"] is not None and (inn.confidence < 0.9 or inn.verified is False):
        review.append("inn")
    review += [k for k in EXPECTED if data[k] is None]
    return HrRecord(
        lang=lang, data=data, scores=scores, needs_review=sorted(set(review), key=HR_FIELDS.index)
    )
