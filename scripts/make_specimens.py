"""Generate FICTIONAL Tajik ID card specimens for testing: uv run python scripts/make_specimens.py -n 20

Every card is drawn on the anonymised templates with invented data, a grey silhouette instead of
a photo and a large "НАМУНА / SPECIMEN" watermark, so it can never pass for a real document.
Output: samples/specimens/<id>_front.jpg, <id>_back.jpg and truth.json (expected fields).
--photo additionally simulates phone photos (background, perspective, blur, JPEG).
"""

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.passport import layout  # noqa: E402
from app.passport.mrz import check_digit  # noqa: E402
from app.passport.translit import to_latin  # noqa: E402

TEMPLATES = ROOT / "app" / "passport" / "templates"

MALE = ["ФАРРУХ", "ДИЛШОД", "БЕҲРУЗ", "СУҲРОБ", "ҶАМШЕД", "ФИРДАВС", "ШАҲРИЁР", "ҚОСИМ", "ҒАЙРАТ", "ӮКТАМ",
        "АБДУҚОДИР", "НАВРӮЗ", "ИСМОИЛ", "ТОҲИР", "ҲУСАЙН"]  # fmt: skip
FEMALE = ["МАДИНА", "ШАҲНОЗА", "ГУЛНОРА", "ЗАРИНА", "МАЛИКА", "ФАРЗОНА", "НИГОРА", "ҲАЛИМА", "ҚУМРӢ",
          "ЁСУМАН",
          "СИТОРА", "МУҲАББАТ", "ТАҲМИНА", "ДИЛНОЗА", "ОЗОДА"]  # fmt: skip
ROOTS = ["РАҲИМ", "КАРИМ", "САЪДУЛЛО", "ҲАКИМ", "НАЗАР", "ҒАФУР", "ҶАЛОЛ", "ШАРИФ", "ҚУРБОН", "ЮСУФ", "ЁҚУБ",
         "ДАВЛАТ", "МАҲМУД", "ОДИНА", "СОЛЕҲ", "ХОЛИҚ", "ЗИЁ"]  # fmt: skip
PLACES = [
    ("СУҒД", ["ХУҶАНД", "ИСТАРАВШАН", "ИСФАРА", "КОНИБОДОМ", "ПАНҶАКЕНТ", "АШТ", "ҒАФУРОВ"]),
    ("ХАТЛОН", ["БОХТАР", "КӮЛОБ", "ВАХШ", "ДАНҒАРА", "ФАРХОР", "ҚУБОДИЁН"]),
]
JAMOATS = ["ГУЛИСТОН", "НАВБАҲОР", "ЧОРКӮҲ", "ДӮСТӢ", "ОБШОРОН", "ЯКДИЛӢ"]
STREETS = ["РӮДАКӢ", "СОМОНӢ", "ФИРДАВСӢ", "ДӮСТӢ", "НАВРӮЗ", "АЙНӢ"]
AUTHORITY = {"ХУҶАНД": ("ШВКД ДАР ШАҲРИ ХУҶАНД", "DIA IN KHUJAND CITY")}

FONT_CANDIDATES = {
    "bold": ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "mono": ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"],
}  # fmt: skip


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    path = next((p for p in FONT_CANDIDATES[kind] if Path(p).exists()), None)
    if path is None:
        raise SystemExit(f"Нет шрифта для '{kind}': {FONT_CANDIDATES[kind]}")
    return ImageFont.truetype(path, size)


def _rand_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randrange((end - start).days))


def fake_person(rng: random.Random, idx: int) -> dict:
    female = rng.random() < 0.5
    first = rng.choice(FEMALE if female else MALE)
    root, father = rng.choice(ROOTS), rng.choice(MALE)
    surname = root + ("ОВА" if female else "ОВ") if rng.random() < 0.8 else root + "ЗОДА"
    patronymic = (father + ("ОВНА" if female else "ОВИЧ")) if rng.random() < 0.7 else father + "ЗОДА"
    region, cities = rng.choice(PLACES)
    city = rng.choice(cities)
    birth = _rand_date(rng, date(1965, 1, 1), date(2007, 12, 31))
    issue = _rand_date(rng, date(2017, 6, 1), date(2025, 12, 31))
    expiry = issue.replace(year=issue.year + 10) - timedelta(days=1)
    reg = _rand_date(rng, date(2005, 1, 1), issue)
    if rng.random() < 0.5:
        street = f"ҶАМОАТИ {rng.choice(JAMOATS)} КӮЧАИ {rng.choice(STREETS)} ХОНАИ {rng.randint(1, 99)}"
    else:
        street = f"МКР {rng.randint(1, 34)} БИНОИ {rng.randint(1, 60)}"
    auth_tg, auth_en = AUTHORITY.get(city, (f"ШВКД ДАР НОҲИЯИ {city}", f"DIA IN {to_latin(city)} DISTRICT"))
    married = rng.random() < 0.5
    return {
        "id": f"specimen_{idx:03d}",
        "surname_tg": surname, "surname_en": to_latin(surname),
        "name_tg": first, "name_en": to_latin(first),
        "patronymic_tg": patronymic, "patronymic_en": to_latin(patronymic),
        "sex": "F" if female else "M",
        "nationality": "TJK", "birth_place": "TJK",
        "birth_date": birth.isoformat(), "issue_date": issue.isoformat(), "expiry_date": expiry.isoformat(),
        "national_id": "35" + "".join(str(rng.randint(0, 9)) for _ in range(11)),
        "document_number": "A" + "".join(str(rng.randint(0, 9)) for _ in range(8)),
        "tax_id": "".join(str(rng.randint(0, 9)) for _ in range(9)),
        "address_lines": [f"ВИЛОЯТИ {region}, {city}", street, f"АЗ {reg:%d.%m.%Y} СОЛ"],
        "region": region, "city_or_district": city,
        "marital_status": ("ОИЛАДОР/MARRIED" if married else "МУҶАРРАД/SINGLE"),
        "issuing_authority_tg": auth_tg, "issuing_authority_en": auth_en,
    }  # fmt: skip


def mrz_lines(p: dict) -> list[str]:
    doc = p["document_number"]
    l1 = f"IDTJK{doc}{check_digit(doc)}{p['national_id']}".ljust(30, "<")
    dob = date.fromisoformat(p["birth_date"]).strftime("%y%m%d")
    exp = date.fromisoformat(p["expiry_date"]).strftime("%y%m%d")
    l2 = f"{dob}{check_digit(dob)}{p['sex']}{exp}{check_digit(exp)}TJK".ljust(29, "<")
    l2 += check_digit(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29])
    l3 = f"{p['surname_en']}<<{p['name_en']}".replace(" ", "<")[:30].ljust(30, "<")
    return [l1, l2, l3]


def _fmt(d: str) -> str:
    return date.fromisoformat(d).strftime("%d.%m.%Y")


def _text(draw: ImageDraw.ImageDraw, z: layout.Zone, text: str, size: int = 26) -> None:
    font = _font("bold", size)
    draw.text((z.x1 + 6, (z.y1 + z.y2) // 2), text, fill=(35, 35, 40), font=font, anchor="lm")


def _silhouette(img: Image.Image, box: tuple[int, int, int, int]) -> None:
    d = ImageDraw.Draw(img)
    x1, y1, x2, y2 = box
    d.rectangle(box, fill=(205, 205, 210))
    cx = (x1 + x2) // 2
    d.ellipse((cx - 55, y1 + 50, cx + 55, y1 + 175), fill=(150, 150, 158))
    d.pieslice((x1 + 20, y1 + 190, x2 - 20, y2 + 160), 180, 360, fill=(150, 150, 158))


def _watermark(img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = _font("bold", 64)
    d.text(
        (img.width // 2, img.height // 2), "НАМУНА · SPECIMEN", font=font, fill=(200, 30, 30, 70), anchor="mm"
    )
    layer = layer.rotate(28, center=(img.width // 2, img.height // 2))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def draw_front(p: dict) -> Image.Image:
    img = Image.open(TEMPLATES / "front.png").convert("RGB")
    _silhouette(img, (60, 190, 355, 540))
    d = ImageDraw.Draw(img)
    f = layout.FRONT
    for key in ("surname_tg", "surname_en", "name_tg", "name_en", "patronymic_tg", "patronymic_en"):
        _text(d, f[key], p[key])
    _text(d, f["sex"], "М/M" if p["sex"] == "M" else "З/F")
    _text(d, f["nationality"], "ТҶК/TJK")
    _text(d, f["birth_date"], _fmt(p["birth_date"]))
    _text(d, f["birth_place"], "ТҶК/TJK")
    _text(d, f["issue_date"], _fmt(p["issue_date"]))
    _text(d, f["expiry_date"], _fmt(p["expiry_date"]))
    _text(d, f["national_id"], p["national_id"])
    mono = _font("mono", 34)
    z = f["document_number"]
    d.text(
        (z.x1 + 8, (z.y1 + z.y2) // 2),
        " ".join(p["document_number"]),
        fill=(35, 35, 40),
        font=mono,
        anchor="lm",
    )
    return _watermark(img)


def draw_back(p: dict) -> Image.Image:
    img = Image.open(TEMPLATES / "back.png").convert("RGB")
    d = ImageDraw.Draw(img)
    b = layout.BACK
    z = b["address"]
    for i, line in enumerate(p["address_lines"]):
        d.text((z.x1 + 6, z.y1 + 8 + i * 30), line, fill=(35, 35, 40), font=_font("bold", 24))
    _text(d, b["marital_status"], p["marital_status"], 24)
    _text(d, b["tax_id"], p["tax_id"], 24)
    _text(d, b["issuing_authority_tg"], p["issuing_authority_tg"], 24)
    _text(d, b["issuing_authority_en"], p["issuing_authority_en"], 24)
    mono = _font("mono", 40)
    for i, line in enumerate(mrz_lines(p)):  # fixed pitch like OCR-B
        for j, ch in enumerate(line):
            d.text((48 + j * 30.5, 434 + i * 50), ch, fill=(30, 30, 35), font=mono, anchor="lm")
    return _watermark(img)


def photo(card: Image.Image, rng: random.Random) -> np.ndarray:
    """Put the card on a table, tilt it, blur and JPEG it like a phone photo."""
    c = cv2.cvtColor(np.asarray(card), cv2.COLOR_RGB2BGR)
    h, w = c.shape[:2]
    H, W = 1500, 2000
    bg = np.full((H, W, 3), rng.choice([(45, 40, 38), (120, 150, 170), (205, 210, 215)]), np.uint8)
    bg = cv2.add(bg, np.random.default_rng(rng.randint(0, 9999)).integers(0, 14, (H, W, 3), dtype=np.uint8))
    s = rng.uniform(1.2, 1.6)
    a = np.deg2rad(rng.uniform(-10, 10) + (180 if rng.random() < 0.15 else 0))
    pts = np.float32([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]) * s
    pts[:2, 0] *= 1 - rng.uniform(0, 0.1)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    dst = (pts @ rot.T + [W / 2, H / 2]).astype(np.float32)
    m = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), dst)
    warped = cv2.warpPerspective(c, m, (W, H))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), m, (W, H))
    out = np.where(mask[..., None] > 0, warped, bg)
    out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.4, 1.1))
    return cv2.imdecode(cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 90)])[1], 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=20, help="сколько карт")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--photo", action="store_true", help="имитировать фото телефоном")
    ap.add_argument("--out", default=str(ROOT / "samples" / "specimens"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    truth = {}
    for i in range(args.n):
        p = fake_person(rng, i)
        for side, card in (("front", draw_front(p)), ("back", draw_back(p))):
            path = out / f"{p['id']}_{side}.jpg"
            if args.photo:
                cv2.imwrite(str(path), photo(card, rng))
            else:
                card.save(path, quality=92)
        truth[p["id"]] = p
    (out / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{args.n} карт -> {out}")


if __name__ == "__main__":
    main()
