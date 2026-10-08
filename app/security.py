"""Optional API key: set API_KEY in .env and send it as the X-API-Key header."""

import hmac
import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_KEY", "").strip()
    if expected and not hmac.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Неверный или отсутствующий X-API-Key")
