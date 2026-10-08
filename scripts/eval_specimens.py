"""Run /hr/passport on generated specimens and compare with truth.json.

uv run python scripts/make_specimens.py -n 30 --photo
uv run python scripts/eval_specimens.py            # samples/specimens
"""

import argparse
import collections
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.hr.mapping import parse_address  # noqa: E402
from app.main import app  # noqa: E402
from app.passport.translit import to_latin  # noqa: E402

GENDER = {"M": {"tg": "Мард", "en": "Male"}, "F": {"tg": "Зан", "en": "Female"}}


def expected(p: dict, lang: str) -> dict:
    tg = lang == "tg"
    addr = parse_address(", ".join(p["address_lines"]))
    conv = (lambda s: s) if tg else to_latin
    ms_tg, ms_en = p["marital_status"].split("/")
    return {
        "surname": p["surname_tg" if tg else "surname_en"].title(),
        "name": p["name_tg" if tg else "name_en"].title(),
        "patronymic": p["patronymic_tg" if tg else "patronymic_en"].title(),
        "gender": GENDER[p["sex"]][lang],
        "date_of_birth": p["birth_date"],
        "address": conv(addr.full),
        "marital_status": (ms_tg if tg else ms_en).title(),
        "region": conv(p["region"]).title(),
        "city_or_district": conv(p["city_or_district"]).title(),
        "inn": p["tax_id"],
        "national_id": p["national_id"],
        "passport_id": p["document_number"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", default=str(ROOT / "samples" / "specimens"))
    ap.add_argument("--lang", default="tg")
    ap.add_argument("-v", action="store_true", help="печатать каждую ошибку")
    args = ap.parse_args()
    folder = Path(args.folder)
    truth = json.loads((folder / "truth.json").read_text(encoding="utf-8"))

    ok, total = collections.Counter(), collections.Counter()
    wrong_but_trusted = 0
    correct_but_flagged = 0
    false_alarm = collections.Counter()
    with TestClient(app) as c:
        for pid, p in truth.items():
            files = {s: open(folder / f"{pid}_{s}.jpg", "rb") for s in ("front", "back")}
            r = c.post(f"/hr/passport?lang={args.lang}", files=files)
            if r.status_code != 200:
                print(pid, r.status_code, r.json())
                continue
            j = r.json()
            for k, exp in expected(p, args.lang).items():
                got = j["data"][k]
                same = (
                    got is not None and difflib.SequenceMatcher(None, got, exp).ratio() >= 0.95
                    if k == "address"
                    else got == exp
                )
                total[k] += 1
                ok[k] += same
                correct_but_flagged += same and k in j["needs_review"]
                if same and k in j["needs_review"]:
                    false_alarm[k] += 1
                if not same:
                    flagged = k in j["needs_review"]
                    wrong_but_trusted += not flagged
                    if args.v:
                        print(
                            f"  {pid} {k}: {got!r} != {exp!r}  "
                            f"{'(в needs_review)' if flagged else '<-- НЕ помечено'}"
                        )
    print(f"{'поле':18s} верно   зря помечено")
    for k in total:
        print(f"{k:18s} {ok[k]:>3}/{total[k]:<4} {false_alarm[k]}")
    n_ok, n_all = sum(ok.values()), sum(total.values())
    print(f"ИТОГО {n_ok}/{n_all} ({n_ok / max(n_all, 1):.1%}),"
          f" ошибок без пометки needs_review: {wrong_but_trusted},"
          f" верных, но помеченных: {correct_but_flagged}")  # fmt: skip


if __name__ == "__main__":
    main()
