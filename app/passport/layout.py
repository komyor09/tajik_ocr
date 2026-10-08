"""Field zones of the Tajik ID card (Шиноснома / Identity Card, 2017+ design) on a 1024x640 card.

Each zone covers the VALUE line only (labels are left out), with a few pixels of slack.
Kinds decide how a zone is read and parsed, see reader.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    x1: int
    y1: int
    x2: int
    y2: int
    kind: str


FRONT: dict[str, Zone] = {
    "surname_tg": Zone(376, 156, 780, 191, "cyr"),
    "surname_en": Zone(376, 186, 780, 219, "lat"),
    "name_tg": Zone(376, 241, 780, 274, "cyr"),
    "name_en": Zone(376, 268, 780, 301, "lat"),
    "patronymic_tg": Zone(376, 324, 780, 358, "cyr"),
    "patronymic_en": Zone(376, 351, 780, 386, "lat"),
    "sex": Zone(376, 418, 452, 454, "sex"),
    "nationality": Zone(452, 418, 596, 454, "code"),
    "birth_date": Zone(596, 418, 796, 454, "date"),
    "birth_place": Zone(796, 418, 1004, 454, "code"),
    "issue_date": Zone(376, 486, 596, 522, "date"),
    "expiry_date": Zone(596, 486, 796, 522, "date"),
    "national_id": Zone(796, 486, 1004, 522, "digits"),
    "document_number": Zone(58, 566, 330, 610, "docnum"),
}

BACK: dict[str, Zone] = {
    "address": Zone(306, 60, 1004, 156, "text_tg"),
    "marital_status": Zone(306, 226, 592, 266, "pair"),
    "blood_group": Zone(590, 226, 800, 266, "blood"),
    "tax_id": Zone(806, 230, 1004, 266, "digits"),
    "issuing_authority_tg": Zone(306, 280, 1004, 313, "cyr_text"),
    "issuing_authority_en": Zone(306, 307, 1004, 341, "lat_text"),
}

# Used to tell sides apart and to detect an upside-down card
FRONT_HEADER = Zone(376, 58, 800, 104, "lat_text")  # "Republic of Tajikistan"
BACK_MRZ = Zone(2, 390, 1022, 580, "mrz")
