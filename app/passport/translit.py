"""Tajik Cyrillic <-> Latin, as printed on Tajik ID cards (ҶОНОВИЧ -> JONOVICH, ЁРМАТОВ -> YORMATOV).

Used to cross-check the Cyrillic name against the Latin one (and the MRZ),
and to repair typical OCR slips in the Cyrillic: lost dots over Ё, Ҷ read as Ч, etc.
"""

import re
from functools import cache

# Every Cyrillic letter -> the Latin spellings seen in practice
TO_LATIN: dict[str, tuple[str, ...]] = {
    "А": ("A",),
    "Б": ("B",),
    "В": ("V",),
    "Г": ("G",),
    "Ғ": ("GH", "G"),
    "Д": ("D",),
    "Е": ("E", "YE"),
    "Ё": ("YO", "IO"),
    "Ж": ("ZH", "J"),
    "З": ("Z",),
    "И": ("I",),
    "Ӣ": ("I", "II"),
    "Й": ("Y", "I"),
    "К": ("K",),
    "Қ": ("Q", "K"),
    "Л": ("L",),
    "М": ("M",),
    "Н": ("N",),
    "О": ("O",),
    "П": ("P",),
    "Р": ("R",),
    "С": ("S",),
    "Т": ("T",),
    "У": ("U",),
    "Ӯ": ("U", "O", "OO"),
    "Ф": ("F",),
    "Х": ("KH", "X"),  # single H is Ҳ
    "Ҳ": ("H",),
    "Ц": ("TS", "C"),
    "Ч": ("CH",),
    "Ҷ": ("J",),
    "Ш": ("SH",),
    "Щ": ("SHCH", "SH"),
    "Ъ": ("", "'"),
    "Ы": ("Y", "I"),
    "Ь": ("",),
    "Э": ("E",),
    "Ю": ("YU", "IU"),
    "Я": ("YA", "IA"),
    "-": ("-", ""),
    " ": (" ", ""),
}

# Letters OCR confuses with each other
CONFUSABLE: dict[str, str] = {
    "Е": "ЁЭ",
    "Ё": "Е",
    "Э": "Е",
    "И": "ЙӢ",
    "Й": "И",
    "Ӣ": "ИЙ",
    "У": "Ӯ",
    "Ӯ": "У",
    "Х": "Ҳ",
    "Ҳ": "Х",
    "Ч": "Ҷ",
    "Ҷ": "Ч",
    "К": "Қ",
    "Қ": "К",
    "Г": "Ғ",
    "Ғ": "Г",
    "Ш": "Щ",
    "Щ": "Ш",
    "Ь": "Ъ",
    "Ъ": "Ь",
    "Л": "ПД",
    "П": "ЛН",
    "Н": "П",
    "Д": "Л",
}

# Latin letters OCR returns inside Cyrillic text
LATIN_LOOKALIKES = str.maketrans("ABCEHKMOPTXYacekopxy", "АВСЕНКМОРТХУасекорху")


def normalize_cyrillic(text: str) -> str:
    return text.translate(LATIN_LOOKALIKES).upper()


# When OCR dropped a letter, these are the likeliest culprits (diacritics get lost first)
_INSERT_ORDER = "ӮӢҶҲҚҒЁ" + "".join(k for k in TO_LATIN if k not in "ӮӢҶҲҚҒЁ -")


def repair(cyrillic: str, latin: str, max_changes: int = 3) -> tuple[str, int] | None:
    """Cheapest edit of `cyrillic` (confusable swaps, a dropped or an extra letter) that makes
    it transliterate exactly to `latin`. Returns (repaired, number_of_edits) or None."""
    cyr = normalize_cyrillic(cyrillic.strip())
    lat = latin.strip().upper().replace("'", "")

    @cache
    def best(i: int, j: int, budget: int) -> tuple[int, str] | None:
        if i == len(cyr) and j == len(lat):
            return (0, "")
        options: list[tuple[int, str]] = []
        if i < len(cyr):
            # keep the letter, or swap it for a confusable one
            for k, letter in enumerate((cyr[i], *CONFUSABLE.get(cyr[i], ""))):
                cost = 0 if k == 0 else 1
                if cost > budget:
                    continue
                for spelling in TO_LATIN.get(letter, (letter,)):
                    if lat.startswith(spelling, j):
                        rest = best(i + 1, j + len(spelling), budget - cost)
                        if rest is not None:
                            # a space/hyphen with no Latin counterpart was invented by OCR: drop it
                            kept = "" if letter in " -" and not spelling else letter
                            options.append((cost + rest[0], kept + rest[1]))
            if budget >= 1:  # OCR invented a letter
                rest = best(i + 1, j, budget - 1)
                if rest is not None:
                    options.append((1 + rest[0], rest[1]))
        if budget >= 1 and j < len(lat):  # OCR dropped a letter
            for letter in _INSERT_ORDER:
                for spelling in TO_LATIN[letter][:1]:  # primary spelling only: K -> К, not Қ
                    if spelling and lat.startswith(spelling, j):
                        rest = best(i, j + len(spelling), budget - 1)
                        if rest is not None:
                            options.append((1 + rest[0], letter + rest[1]))
        return min(options, key=lambda o: o[0]) if options else None  # min keeps the first on ties

    result = best(0, 0, max_changes)
    return (result[1], result[0]) if result else None


def to_latin(cyrillic: str) -> str:
    """Primary transliteration (ЗУЛҲАҶОН -> ZULHAJON)."""
    return "".join(TO_LATIN.get(c, (c,))[0] for c in normalize_cyrillic(cyrillic))


def matches(cyrillic: str, latin: str) -> bool:
    return repair(cyrillic, latin, max_changes=0) is not None


# Words that appear in addresses and issuing authorities on Tajik ID cards
_ADDRESS_WORDS = """
ВИЛОЯТИ НОҲИЯИ НОҲИЯ ШАҲРИ ШАҲР ҶАМОАТИ ДЕҲАИ ДЕҲА ҚИШЛОҚИ КӮЧАИ КӮЧА ХОНАИ ХОНА ҲАВЛИИ МАҲАЛЛАИ
ГУЗАРИ ХИЁБОНИ БИНОИ ДАР АЗ СОЛ СОЛИ ШВКД ШММ ВКД ВМКБ НТМ МАРКАЗИ ТОБЕИ ҶУМҲУРӢ
"""
# Regions, cities and districts of Tajikistan (multi-word names split into words)
_PLACES = """
СУҒД ХАТЛОН ДУШАНБЕ ВМКБ НТМ БАДАХШОН
ХУҶАНД ИСТАРАВШАН ИСФАРА КОНИБОДОМ ПАНҶАКЕНТ ГУЛИСТОН ҚАЙРОҚҚУМ БӮСТОН ЧКАЛОВСК АШТ ҒАФУРОВ БОБОҶОН
ҶАББОР РАСУЛОВ СПИТАМЕН МАСТЧОҲ МАСЧОҲ КӮҲИСТОНИ ДЕВАШТИЧ ШАҲРИСТОН ЗАФАРОБОД АЙНӢ ТАБОШАР
БОХТАР КӮЛОБ НОРАК ЛЕВАКАНД ВАХШ ДАНҒАРА ФАРХОР ВОСЕЪ ҲАМАДОНӢ МӮЪМИНОБОД БАЛҶУВОН ХОВАЛИНГ
ШАМСИДДИН ШОҲИН ТЕМУРМАЛИК ҚУБОДИЁН ШАҲРИТУС НОСИРИ ХУСРАВ ҶАЙҲУН ДӮСТӢ ПАНҶ ҶАЛОЛИДДИНИ БАЛХӢ
ХУРОСОН АБДУРАҲМОНИ ҶОМӢ КУШОНИЁН ЁВОН ВАҲДАТ ҲИСОР ТУРСУНЗОДА РӮДАКӢ ШАҲРИНАВ ВАРЗОБ ФАЙЗОБОД
РОҒУН НУРОБОД РАШТ ТОҶИКОБОД ЛАХШ САНГВОР ХОРУҒ ВАНҶ ДАРВОЗ ИШКОШИМ МУРҒОБ РОШТҚАЛЪА РӮШОН ШУҒНОН
СИНО ФИРДАВСӢ ИСМОИЛИ СОМОНӢ ШОҲМАНСУР НАВБАҲОР
"""
PLACES = frozenset(_PLACES.split())
LEXICON = frozenset(_ADDRESS_WORDS.split()) | PLACES
# Address words that are often glued to the next word by OCR ("ВИЛОЯТИСУҒД")
_GLUE_PREFIXES = ("ВИЛОЯТИ", "ҶАМОАТИ", "НОҲИЯИ", "ШАҲРИ", "КӮЧАИ", "ХОНАИ", "БИНОИ", "ДЕҲАИ")


def _closest(word: str, lexicon: frozenset[str], cutoff: float) -> str | None:
    import difflib

    m = difflib.get_close_matches(word, lexicon, n=1, cutoff=cutoff)
    return m[0] if m else None


def fix_words(text: str, lexicon: frozenset[str] = LEXICON) -> str:
    """Repair address words against a lexicon of address terms and place names:
    one confusable letter (НОХИЯИ -> НОҲИЯИ), a close misreading of a long word
    (ЗИДОЯТИ -> ВИЛОЯТИ, КОНИРОДОМ -> КОНИБОДОМ) and glued words (ВИЛОЯТИХАТЛОН)."""

    def fix(word: str) -> str:
        if word in lexicon or len(word) < 3:
            return word
        for pos in range(len(word)):
            for alt in CONFUSABLE.get(word[pos], ""):
                candidate = word[:pos] + alt + word[pos + 1 :]
                if candidate in lexicon:
                    return candidate
        keyword = _closest(word, frozenset(_GLUE_PREFIXES), 0.7)  # frequent address terms: looser match
        if keyword:
            return keyword
        for prefix in _GLUE_PREFIXES:  # glued: fuzzy prefix + a real word
            head, tail = word[: len(prefix)], word[len(prefix) :]
            if len(tail) >= 3 and _closest(head, frozenset({prefix}), 0.7):
                return f"{prefix} {fix(tail)}"
        if len(word) >= 5:
            return _closest(word, lexicon, 0.8) or word
        return word

    return re.sub(r"[А-ЯЁҒӢҚӮҲҶ]+", lambda m: fix(m.group(0)), text)
