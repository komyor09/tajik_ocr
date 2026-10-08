"""Read the Tajik ID card: zone OCR per field, MRZ, and cross-checks between them."""

import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import cv2
import numpy as np

from app import tess
from app.passport import card as cardmod
from app.passport import layout, mrz, translit
from app.passport.align import align
from app.passport.mrz import Mrz
from app.preprocess import deskew, flatten_lighting

LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
COUNTRY_CODES = [
    "TJK",
    "RUS",
    "UZB",
    "KGZ",
    "KAZ",
    "TKM",
    "AFG",
    "IRN",
    "UKR",
    "BLR",
    "AZE",
    "ARM",
    "GEO",
    "MDA",
    "CHN",
    "TUR",
    "PAK",
    "IND",
    "USA",
    "DEU",
    "GBR",
]

OPTIONAL = {"blood_group"}  # often left blank on the card

_pool = ThreadPoolExecutor(max_workers=4)  # tesseract runs as a subprocess, threads parallelise it


@dataclass
class Field:
    value: str | None
    raw: str
    confidence: float
    verified: bool | None = None  # True: confirmed by MRZ/cross-check, False: contradicts it
    note: str | None = None


@dataclass
class SideResult:
    side: str | None = None  # "front" | "back"
    fields: dict[str, Field] = field(default_factory=dict)
    mrz: Mrz | None = None
    method: str = "none"  # how the card was located: "template" | "contour" | "none"
    match_score: int = 0  # template keypoint inliers
    rotated: bool = False
    recognized: bool = True


# ---------------------------------------------------------------- zone OCR


def _crop(gray: np.ndarray, z: layout.Zone, single_line: bool = True) -> np.ndarray:
    """Cut the zone and tighten it to the ink. For one-line fields keep only the strongest text
    band, so a clipped label edge above/below the value does not confuse tesseract."""
    crop = gray[z.y1 : z.y2, z.x1 : z.x2]
    ink = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if single_line:
        rows = ink.sum(axis=1) / 255
        bands, start = [], None
        for y, v in enumerate(np.append(rows, 0)):
            if v > 1 and start is None:
                start = y
            elif v <= 1 and start is not None:
                bands.append((start, y))
                start = None
        if bands:
            y1, y2 = max(bands, key=lambda b: rows[b[0] : b[1]].sum())
            ink[: max(0, y1)] = 0
            ink[y2:] = 0
    ys, xs = np.where(ink > 0)
    if len(xs) > 20:
        crop = crop[max(0, ys.min() - 4) : ys.max() + 5, max(0, xs.min() - 4) : xs.max() + 5]
    return crop


def _ocr(
    gray: np.ndarray, z: layout.Zone, lang: str, psm: int = 7, whitelist: str | None = None, scales=(2.0, 3.0)
) -> tuple[str, float]:
    crop = _crop(gray, z, single_line=psm == 7)
    text, conf = "", 0.0
    for s in scales:  # small bold text sometimes needs a bigger scale
        img = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        img = cv2.copyMakeBorder(img, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
        text, conf, _ = tess.read(img, lang, psm=psm, whitelist=whitelist)
        if text.strip():
            break
    return text.strip(), conf


def _parse_date(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[4:]), int(digits[2:4]), int(digits[:2])).isoformat()
    except ValueError:
        return None


# Latin letters OCR mixes up in country codes: substituting them is cheap
_CHEAP = {frozenset(p) for p in ("IJ", "LJ", "IL", "OQ", "OD", "UV", "MN", "0O", "1I")}


def _match_code(raw: str) -> str | None:
    """'TYKITIK' / 'TUK/TLK' (= ТҶК/TJK) -> 'TJK'. Compares the last 3 letters with known codes."""
    tail = re.sub(r"[^A-Z0-9]", "", raw.split("/")[-1].upper())[-3:]
    if len(tail) < 3:
        return None

    def cost(code: str) -> float:
        return sum(
            0 if a == b else 0.3 if frozenset((a, b)) in _CHEAP else 1
            for a, b in zip(tail, code, strict=False)
        )

    best = min(COUNTRY_CODES, key=cost)
    return best if cost(best) <= 0.6 else None  # only cheap I/J-style slips, no real letter changes


CYRILLIC_CODES = {"ТҶК": "TJK"}


def _match_code_cyr(raw: str) -> str | None:
    """'ТЧК/ТЛК' read with the Tajik model -> 'TJK' (only codes we know in Cyrillic)."""
    head = translit.normalize_cyrillic(raw.split("/")[0])
    head = re.sub(r"[^А-ЯЁҒӢҚӮҲҶ]", "", head)[:3]
    for cyr, code in CYRILLIC_CODES.items():
        if len(head) == 3 and all(
            a == b or b in translit.CONFUSABLE.get(a, "") for a, b in zip(head, cyr, strict=False)
        ):
            return code
    return None


MARITAL_TG = ["МУҶАРРАД", "ОИЛАДОР", "ЗАНДОР", "ШАВҲАРДОР", "ҶУДОШУДА", "БЕВА", "ЗАНМУРДА"]
MARITAL_EN = ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "WIDOW", "WIDOWER"]


def _vocab(text: str, words: list[str]) -> str | None:
    """Closest vocabulary word to the start of `text` (OCR often glues junk to the end)."""
    if not text:
        return None
    for w in words:  # "MYYAPPAJLYSINGLE": the word is inside the junk
        if w in text:
            return w
    scored = [(difflib.SequenceMatcher(None, w, text[: len(w)]).ratio(), w) for w in words]
    score, word = max(scored)
    return word if score >= 0.6 else text


# After these words comes a number: "БИНОИ ЗБ" is "БИНОИ 36"
_NUMBERED = r"(БИНОИ|ХОНАИ|ХОНА|МАХ|МКР|КВ|КВАРТИРАИ|№)"
_DIGIT_LOOKALIKES = str.maketrans("ЗБОЧТ", "36047")


def _clean_tg(line: str) -> str:
    line = translit.normalize_cyrillic(line)
    line = re.sub(r"[^А-ЯЁҒӢҚӮҲҶ0-9\-.,/№ ]", "", line)
    line = translit.fix_words(re.sub(r"\s+", " ", line).strip(" ,."))
    return re.sub(
        _NUMBERED + r" ([0-9ЗБОЧТ]{1,4})\b",
        lambda m: (
            f"{m.group(1)} {m.group(2).translate(_DIGIT_LOOKALIKES)}"
            if re.search(r"\d", m.group(2)) or len(m.group(2)) <= 2
            else m.group(0)
        ),
        line,
    )


def _read_zone(gray: np.ndarray, name: str, z: layout.Zone) -> Field:
    k = z.kind
    if k == "cyr":
        raw, conf = _ocr(gray, z, "tgk")
        value = re.sub(r"[^А-ЯЁҒӢҚӮҲҶ\- ]", "", translit.normalize_cyrillic(raw)).strip()
        return Field(value or None, raw, conf)
    if k == "lat":  # no whitelist: it would drop spaces ("ABDU RAHMON")
        raw, conf = _ocr(gray, z, "eng")
        return Field(re.sub(r"[^A-Z\- ]", "", raw.upper()).strip() or None, raw, conf)
    if k == "date":
        raw, conf = _ocr(gray, z, "eng", whitelist=DIGITS + ".")
        value = _parse_date(raw)
        return Field(value, raw, conf, note=None if value else "дата не распознана")
    if k == "digits":
        raw, conf = _ocr(gray, z, "eng")  # whitelisted reads report confidence 0, so try plain first
        if len(re.sub(r"\D", "", raw)) < 6:
            raw, conf = _ocr(gray, z, "eng", whitelist=DIGITS)
        return Field(re.sub(r"\D", "", raw) or None, raw, conf)
    if k == "docnum":
        raw, conf = _ocr(gray, z, "eng", whitelist=LATIN + DIGITS)
        v = re.sub(r"[^A-Z0-9]", "", raw)
        if len(v) == 9:  # letter + 8 digits
            v = mrz.TO_ALPHA.get(v[0], v[0]) + "".join(mrz.TO_DIGIT.get(c, c) for c in v[1:])
        return Field(v or None, raw, conf)
    if k == "sex":
        raw, conf = _ocr(gray, z, "eng", whitelist="MF/")
        v = raw.replace("/", "")[-1:] or None
        return Field(v if v in ("M", "F") else None, raw, conf)
    if k == "code":
        raw, conf = _ocr(gray, z, "eng", whitelist=LATIN + "/")
        code = _match_code(raw)
        if code is None:  # bold, blurry codes (place of birth) read better as a single word
            raw, conf = _ocr(gray, z, "eng", psm=8, whitelist=LATIN + "/", scales=(2.0,))
            code = _match_code(raw)
        if code is None:
            raw_tg, conf = _ocr(gray, z, "tgk")
            code, raw = _match_code_cyr(raw_tg), f"{raw} | {raw_tg}"
        return Field(code, raw, conf, note="сопоставлено со списком кодов" if code else "код не распознан")
    if k == "pair":  # МУҶАРРАД/SINGLE: closed vocabulary, matched by prefix
        raw_tg, conf_tg = _ocr(gray, z, "tgk")
        raw_en, conf_en = _ocr(gray, z, "eng")
        tg = _vocab(
            re.sub(r"[^А-ЯЁҒӢҚӮҲҶ]", "", translit.normalize_cyrillic(raw_tg.split("/")[0])), MARITAL_TG
        )
        en = _vocab(re.sub(r"[^A-Z]", "", raw_en.upper().split("/")[-1]), MARITAL_EN)
        value = f"{tg}/{en}" if tg and en else (tg or en or None)
        return Field(value, f"{raw_tg} | {raw_en}", round((conf_tg + conf_en) / 2, 4))
    if k == "blood":
        raw, conf = _ocr(gray, z, "eng", whitelist="ABOIV0()+-/")
        m = re.search(r"\b(O|0|A|B|AB)?\s*\(?(I{1,3}|IV)\)?\s*(Rh)?\s*([+-])", raw)
        if not m or conf < 0.6 or len(re.sub(r"\W", "", m.group(0))) < 2:  # blank field -> noise
            return Field(None, raw, conf)
        return Field(m.group(0).replace(" ", ""), raw, conf)
    if k == "text_tg":
        raw, conf = _ocr(gray, z, "tgk", psm=6)
        # the caption "Нишонӣ / Address" may peek into the zone on some cards
        lines = [
            _clean_tg(ln)
            for ln in raw.splitlines()
            if not re.search(r"НИШОН|ADDR|ADD?RE|/\s*А[ДЛ]", ln.upper())
        ]
        return Field(", ".join(ln for ln in lines if ln) or None, raw, conf)
    if k == "cyr_text":
        raw, conf = _ocr(gray, z, "tgk")
        return Field(_clean_tg(raw) or None, raw, conf)
    if k == "lat_text":
        raw, conf = _ocr(gray, z, "eng")
        value = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9\-.,/ ]", "", raw.upper())).strip()
        return Field(value or None, raw, conf)
    raise ValueError(f"unknown zone kind {k}")


def _read_zones(gray: np.ndarray, zones: dict[str, layout.Zone]) -> dict[str, Field]:
    futures = {name: _pool.submit(_read_zone, gray, name, z) for name, z in zones.items()}
    return {name: f.result() for name, f in futures.items()}


def _gray(card_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(flatten_lighting(card_bgr), cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------- sides


def _looks_like_front(gray: np.ndarray) -> bool:
    raw, _ = _ocr(gray, layout.FRONT_HEADER, "eng", scales=(1.5,))
    return bool(re.search(r"REPUB|TAJIK|STAN", raw.upper()))


_NAMES_LINE = re.compile(r"[A-Z]+(<[A-Z]+)*<<[A-Z]+(<[A-Z]+)*<*")


def _names_ok(m: Mrz | None) -> bool:
    return m is not None and bool(_NAMES_LINE.fullmatch(m.lines[2]))


def _mrz_score(m: Mrz | None) -> int:
    if m is None:
        return -1
    return 2 * sum(m.checks.values()) + (m.document_type == "ID") + _names_ok(m)


def _read_mrz(gray: np.ndarray) -> Mrz | None:
    """The MRZ sits low on the card where the template has few keypoints, so the warp can be a
    few pixels off there. Re-straighten the band locally and try several reads; the check digits
    tell which one is right. The names line has no check digit: it is taken from any read where
    it looks like SURNAME<<GIVEN<NAMES."""
    z = layout.BACK_MRZ
    band = gray[z.y1 : z.y2, z.x1 : z.x2]
    straight, _ = deskew(cv2.cvtColor(band, cv2.COLOR_GRAY2BGR), max_angle=6)
    straight = cv2.cvtColor(straight, cv2.COLOR_BGR2GRAY)
    variants = [
        straight,
        cv2.resize(straight, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA),
        cv2.threshold(straight, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1],
        band,
        cv2.resize(straight, None, fx=1.3, fy=1.3, interpolation=cv2.INTER_CUBIC),
    ]
    best: Mrz | None = None
    names_line: str | None = None
    for img in variants:
        img = cv2.copyMakeBorder(img, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
        raw, _, _ = tess.read(img, "ocrb", psm=6, whitelist=LATIN + DIGITS + "<")
        lines = mrz.clean_lines(raw)
        m = mrz.parse(lines) if lines else None
        if names_line is None and _names_ok(m):
            names_line = m.lines[2]
        if _mrz_score(m) > _mrz_score(best):
            best = m
        if _mrz_score(best) == 10:  # all 4 checks + ID + clean names line
            break
    if best is not None and not _names_ok(best) and names_line:
        best = mrz.parse(best.lines[:2] + [names_line])
    return best


def _plausible(m: Mrz | None) -> bool:
    """Real TD1 MRZ, not random text squeezed into 3 lines."""
    return m is not None and m.document_type == "ID" and sum(m.checks.values()) >= 2


def _read_side(gray: np.ndarray, side: str) -> tuple[dict[str, Field], Mrz | None]:
    if side == "front":
        return _read_zones(gray, layout.FRONT), None
    m = _read_mrz(gray)
    return _read_zones(gray, layout.BACK), m if _plausible(m) else None


def _fallback(image_bgr: np.ndarray) -> SideResult:
    """No template match (very blurry/partial picture): card contour + header/MRZ checks."""
    card, _ = cardmod.normalize(image_bgr)
    for rotated in (False, True):
        gray = _gray(cardmod.rotate180(card) if rotated else card)
        if _looks_like_front(gray):
            return SideResult("front", _read_zones(gray, layout.FRONT), method="contour", rotated=rotated)
        m = _read_mrz(gray)
        if _plausible(m):
            return SideResult("back", _read_zones(gray, layout.BACK), m, method="contour", rotated=rotated)
    return SideResult(recognized=False)


def read_card(image_bgr: np.ndarray) -> SideResult:
    """Find the card on the picture, decide which side it is, read its fields."""
    a = align(image_bgr)
    if a is None:
        return _fallback(image_bgr)
    fields, m = _read_side(_gray(a.card), a.side)
    return SideResult(a.side, fields, m, method="template", match_score=a.inliers, rotated=a.rotated)


# ---------------------------------------------------------------- cross-checks


def _check(f: Field | None, trusted: str | None, source: str) -> Field:
    """Compare a field with a trusted value (MRZ with valid check digit). The trusted value wins."""
    if trusted is None:
        return f or Field(None, "", 0.0)
    if f is None or f.value is None:
        return Field(trusted, f.raw if f else "", 1.0, True, f"взято из {source}")
    if f.value == trusted:
        f.verified = True
        return f
    return Field(trusted, f.raw, f.confidence, True, f"исправлено по {source} (было {f.value})")


def _same_name(a: str, b: str) -> bool:
    a, b = a.replace(" ", ""), b.replace(" ", "")
    return a == b or (len(b) >= 25 and a.startswith(b))  # the MRZ truncates long names


def _resolve_name(fields: dict[str, Field], key: str, mrz_name: str | None) -> None:
    """Up to three independent reads of a name: Cyrillic and Latin on the front, Latin in the MRZ
    (no check digit for names). The Latin candidate that the Cyrillic transliterates into with
    the fewest edits wins; both spellings are then fixed and confirmed."""
    cyr, en = fields.get(f"{key}_tg"), fields.get(f"{key}_en")
    candidates: list[tuple[str, str]] = []
    if en and en.value:
        candidates += [(en.value, "латинице"), (en.value.replace(" ", ""), "латинице")]
    if mrz_name:
        candidates.append((mrz_name, "MRZ"))
    if not candidates:
        if cyr and cyr.value:  # nothing to compare with: offer a transliteration, unverified
            fields[f"{key}_en"] = Field(
                translit.to_latin(cyr.value), en.raw if en else "", 0.0, None, "транслитерация кириллицы"
            )
        return
    if en is None or en.value is None:  # front missing or unreadable: take the MRZ
        fields[f"{key}_en"] = en = Field(mrz_name, en.raw if en else "", 1.0, None, "взято из MRZ")

    best: tuple[int, str, str, str] | None = None  # edits, latin, fixed cyrillic, source
    if cyr and cyr.value:
        for lat, source in candidates:
            r = translit.repair(cyr.value, lat)
            if r and (best is None or r[1] < best[0]):
                best = (r[1], lat, r[0], source)

    if best is not None:
        _, lat, fixed, source = best
        if fixed != cyr.value:
            cyr.note = f"исправлено по {source} (было {cyr.value})"
            cyr.value = fixed
        cyr.verified = True
        if lat != en.value:
            en.note = (
                f"исправлено по {'кириллице и MRZ' if source == 'MRZ' else 'кириллице'} (было {en.value})"
            )
            en.value = lat
        en.verified = True
        return

    # Cyrillic does not fit any Latin reading
    if cyr and cyr.value:
        cyr.verified = False
        cyr.note = f"не совпадает с латиницей {en.value}"
    if mrz_name and en.value and not _same_name(en.value, mrz_name):
        en.verified = False
        en.note = f"в MRZ: {mrz_name}"
    elif mrz_name:
        en.verified = True


LOW_MATCH = 40  # template keypoints: below this the picture is blurry, small or partly covered


def merge(front: SideResult | None, back: SideResult | None) -> tuple[dict[str, Field], list[str]]:
    fields: dict[str, Field] = {}
    warnings: list[str] = []
    for name, side in (("лицевой", front), ("обратной", back)):
        if side and side.method == "template" and side.match_score < LOW_MATCH:
            warnings.append(f"низкое качество снимка {name} стороны — лучше переснять ближе и резче")
    if front:
        fields |= front.fields
    if back:
        fields |= back.fields

    m = back.mrz if back else None
    if m is not None:
        if not m.valid:
            failed = [k for k, ok in m.checks.items() if not ok]
            warnings.append(f"MRZ: не сошлись контрольные цифры ({', '.join(failed)})")
        c = m.checks
        if c["document_number"]:
            fields["document_number"] = _check(fields.get("document_number"), m.document_number, "MRZ")
        if c["birth_date"] and m.birth_date:
            fields["birth_date"] = _check(fields.get("birth_date"), m.birth_date.isoformat(), "MRZ")
        if c["expiry_date"] and m.expiry_date:
            fields["expiry_date"] = _check(fields.get("expiry_date"), m.expiry_date.isoformat(), "MRZ")
        if m.valid:  # composite check covers these
            fields["sex"] = _check(fields.get("sex"), m.sex, "MRZ")
            fields["nationality"] = _check(fields.get("nationality"), m.nationality, "MRZ")
            if m.optional1:
                fields["national_id"] = _check(fields.get("national_id"), m.optional1, "MRZ")

    mrz_names = m is not None and _names_ok(m)
    if m is not None and not mrz_names:
        warnings.append("MRZ: строка с именами не прочитана")
    names = {
        "surname": m.surname if mrz_names else None,
        "name": m.given_names if mrz_names else None,
        "patronymic": None,
    }
    for key, mrz_name in names.items():
        _resolve_name(fields, key, mrz_name or None)

    # Tajik ID cards are valid for 10 years: expiry = issue + 10 years - 1 day
    issue, expiry = fields.get("issue_date"), fields.get("expiry_date")
    if issue and expiry and issue.value and expiry.value:
        i = date.fromisoformat(issue.value)
        try:
            expected = (i.replace(year=i.year + 10) - timedelta(days=1)).isoformat()
        except ValueError:
            expected = None
        if expected == expiry.value:
            issue.verified = True
            expiry.verified = expiry.verified if expiry.verified is not None else True
        else:
            warnings.append("дата выдачи и срок действия не дают 10 лет — проверь вручную")

    for name, f in fields.items():
        if f.value is None and name not in OPTIONAL:
            warnings.append(f"поле {name} не распознано")
    return fields, warnings


def mrz_dict(m: Mrz | None) -> dict | None:
    if m is None:
        return None
    d = asdict(m)
    d["birth_date"] = m.birth_date.isoformat() if m.birth_date else None
    d["expiry_date"] = m.expiry_date.isoformat() if m.expiry_date else None
    d["valid"] = m.valid
    return d
