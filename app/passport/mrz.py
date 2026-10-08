"""TD1 machine-readable zone (ID cards: 3 lines x 30 chars), ICAO Doc 9303 part 5.

Line 1: doc type(2) issuer(3) doc number(9) check(1) optional(15)
Line 2: birth YYMMDD(6) check(1) sex(1) expiry YYMMDD(6) check(1) nationality(3)
        optional(11) composite check(1)
Line 3: SURNAME<<GIVEN<NAMES (30)
"""

import itertools
import re
from dataclasses import dataclass, field
from datetime import date

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"

# OCR confusions, resolved by the field type at each position
TO_DIGIT = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "U": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
    "T": "7",
}
TO_ALPHA = {v: k for k, v in TO_DIGIT.items() if k not in "QDUL"} | {"0": "O", "1": "I", "8": "B"}
AMBIGUOUS = {
    "0": "O",
    "O": "0",
    "1": "I",
    "I": "1",
    "8": "B",
    "B": "8",
    "5": "S",
    "S": "5",
    "2": "Z",
    "Z": "2",
    "6": "G",
    "G": "6",
}


def check_digit(s: str) -> str:
    values = {c: i for i, c in enumerate("0123456789")} | {
        c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    }
    values["<"] = 0
    return str(sum(values.get(c, 0) * w for c, w in zip(s, itertools.cycle((7, 3, 1)))) % 10)


@dataclass
class Mrz:
    lines: list[str]
    document_type: str
    issuer: str
    document_number: str
    optional1: str
    birth_date: date | None
    sex: str | None
    expiry_date: date | None
    nationality: str
    optional2: str
    surname: str
    given_names: str
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return all(self.checks.values())


def clean_lines(text: str) -> list[str] | None:
    """Pick the 3 MRZ lines out of raw OCR text and normalise them to 30 chars."""
    text = text.upper().replace("«", "<<").replace("‹", "<").replace(" ", "")
    lines = [re.sub(r"[^A-Z0-9<]", "", ln) for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) >= 20]
    if len(lines) < 3:
        return None
    lines = lines[-3:]
    return [(ln + "<" * 30)[:30] for ln in lines]


def _digits(s: str) -> str:
    return "".join(TO_DIGIT.get(c, c) for c in s)


def _alpha(s: str) -> str:
    return "".join(TO_ALPHA.get(c, c) for c in s)


def _fix_with_check(value: str, check: str) -> str:
    """Alphanumeric field (document number): try O/0, I/1... swaps until the check digit matches.

    The Tajik format (one letter + 8 digits, e.g. A12345678) is tried first: a random mix of
    O and 0 can pass the checksum by coincidence.
    """
    tajik = _alpha(value[0]) + _digits(value[1:])
    if tajik[1:].isdigit() and check_digit(tajik) == check:
        return tajik
    if check_digit(value) == check:
        return value
    positions = [i for i, c in enumerate(value) if c in AMBIGUOUS]
    for n in (1, 2):
        for combo in itertools.combinations(positions, n):
            candidate = list(value)
            for i in combo:
                candidate[i] = AMBIGUOUS[candidate[i]]
            candidate = "".join(candidate)
            if check_digit(candidate) == check:
                return candidate
    return value


def _date(yymmdd: str, *, future: bool) -> date | None:
    if not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    today = date.today()
    if future:  # expiry dates are within ~this century
        year = 2000 + yy
    else:  # a birth date cannot be in the future
        year = 2000 + yy if 2000 + yy <= today.year else 1900 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def parse(lines: list[str]) -> Mrz:
    l1, l2, l3 = lines
    # Position-aware cleanup
    l1 = _alpha(l1[:5]) + l1[5:14] + _digits(l1[14]) + l1[15:]
    if l1[2:5] == "TJK":  # Tajik cards keep the 13-digit national ID in optional data
        l1 = l1[:15] + "".join(c if c == "<" else TO_DIGIT.get(c, c) for c in l1[15:])
    l2 = _digits(l2[:7]) + l2[7] + _digits(l2[8:15]) + _alpha(l2[15:18]) + l2[18:29] + _digits(l2[29])
    l3 = _alpha(l3)

    doc_number = _fix_with_check(l1[5:14], l1[14])
    l1 = l1[:5] + doc_number + l1[14:]

    names = l3.rstrip("<").split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""

    checks = {
        "document_number": check_digit(l1[5:14]) == l1[14],
        "birth_date": check_digit(l2[0:6]) == l2[6],
        "expiry_date": check_digit(l2[8:14]) == l2[14],
        "composite": check_digit(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]) == l2[29],
    }
    sex = {"M": "M", "F": "F"}.get(l2[7])
    return Mrz(
        lines=[l1, l2, l3],
        document_type=l1[0:2].replace("<", ""),
        issuer=l1[2:5],
        document_number=doc_number.replace("<", ""),
        optional1=l1[15:30].replace("<", ""),
        birth_date=_date(l2[0:6], future=False),
        sex=sex,
        expiry_date=_date(l2[8:14], future=True),
        nationality=l2[15:18],
        optional2=l2[18:29].replace("<", ""),
        surname=surname,
        given_names=given,
        checks=checks,
    )
