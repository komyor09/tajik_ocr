"""Read a Tajik ID card from one or two pictures. Shared by /passport and /hr."""

from dataclasses import dataclass, field

import numpy as np

from app import tess
from app.config import Settings
from app.passport import reader
from app.passport.mrz import Mrz


class CardNotFound(Exception):
    """No Tajik ID card on any of the pictures."""


@dataclass
class PassportResult:
    fields: dict[str, reader.Field]
    mrz: Mrz | None
    sides: dict[str, reader.SideResult]
    warnings: list[str] = field(default_factory=list)


def read_passport(images: list[tuple[str, np.ndarray]], settings: Settings) -> PassportResult:
    """images: (upload field name, BGR array). The side is detected from the picture itself,
    so it does not matter which file was sent as front or back.

    Raises RuntimeError if Tesseract or a model is missing, CardNotFound if no card is found.
    """
    tess.init(settings.tesseract_cmd)
    for lang in ("tgk", "eng", "ocrb"):
        tess.langs_location(lang)  # clear error if a model is missing

    sides: dict[str, reader.SideResult] = {}
    warnings: list[str] = []
    for upload, img in images:
        r = reader.read_card(img)
        if not r.recognized:
            warnings.append(f"файл '{upload}': ID-карта не найдена")
        elif r.side in sides:
            warnings.append(f"файл '{upload}': повторно прислана сторона {r.side}, взята первая")
        else:
            if upload in ("front", "back") and upload != r.side:
                warnings.append(f"файл '{upload}' оказался стороной {r.side}")
            sides[r.side] = r
    if not sides:
        raise CardNotFound("На изображении не найдена таджикская ID-карта")

    fields, merge_warnings = reader.merge(sides.get("front"), sides.get("back"))
    back = sides.get("back")
    return PassportResult(
        fields=fields,
        mrz=back.mrz if back else None,
        sides=sides,
        warnings=warnings + merge_warnings,
    )
