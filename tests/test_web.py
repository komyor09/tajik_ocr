"""Website: pages are served and every UI string exists in all four languages."""

import json
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web.router import STATIC_DIR, mount_web

LANGS = ["tg", "uz", "ru", "en"]


def _client() -> TestClient:
    app = FastAPI()
    mount_web(app)
    return TestClient(app)


def _strings() -> dict[str, list[str]]:
    src = (STATIC_DIR / "js" / "i18n.js").read_text(encoding="utf-8")
    body = src.split("window.I18N = ", 1)[1].rsplit(";", 1)[0]
    return json.loads(body)


def test_pages_and_assets_are_served():
    client = _client()
    for path in ("/", "/try"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
    assets = (
        "css/site.css", "js/i18n.js", "js/site.js", "js/try.js", "js/landing.js",
        "img/hero.svg", "img/logo.svg",
        "demo/card_front.webp", "demo/card_back.webp", "demo/card_preview.webp", "demo/text.webp",
    )  # fmt: skip
    for asset in assets:
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_languages_declared():
    src = (STATIC_DIR / "js" / "i18n.js").read_text(encoding="utf-8")
    assert f"window.I18N_LANGS = {json.dumps(LANGS)};" in src


def test_every_string_translated():
    for key, row in _strings().items():
        assert len(row) == len(LANGS), key
        assert all(isinstance(s, str) and s.strip() for s in row), key


def test_html_uses_only_known_keys():
    strings = _strings()
    used = set()
    for page in ("index.html", "try.html"):
        html = (STATIC_DIR / page).read_text(encoding="utf-8")
        used |= set(re.findall(r'data-i18n(?:-ph|-title)?="([^"]+)"', html))
        used |= set(re.findall(r'data-title-key="([^"]+)"', html))
    missing = used - strings.keys()
    assert not missing, missing


def test_hr_field_labels_cover_api_fields():
    from app.hr.mapping import HR_FIELDS

    strings = _strings()
    assert not [f for f in HR_FIELDS if f"f.{f}" not in strings]
