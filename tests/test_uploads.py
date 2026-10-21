"""Upload checks (413, 415) work without Tesseract: they happen before any OCR."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app

client = TestClient(app)  # no `with`: lifespan (Tesseract, models) is not started


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_wrong_type_is_415():
    r = client.post("/ocr", files={"file": ("doc.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_not_an_image_is_415():
    r = client.post("/ocr", files={"file": ("fake.png", b"not really a png", "image/png")})
    assert r.status_code == 415


def test_too_big_is_413():
    big = b"0" * (get_settings().max_upload_mb * 1024 * 1024 + 1)
    r = client.post("/ocr", files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 413


def test_empty_is_400():
    files = {"front": ("a.png", b"", "image/png"), "back": ("b.png", _png(), "image/png")}
    r = client.post("/hr/passport", files=files)
    assert r.status_code == 400


def test_swagger_is_served():
    assert client.get("/docs").status_code == 200
    assert "/ocr" in client.get("/openapi.json").json()["paths"]
