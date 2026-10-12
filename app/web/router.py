"""Website: the landing page (/) and the no-code playground (/try), in tg/uz/ru/en.

Plain static files, no build step and no external CDNs or fonts — the service is meant to run
offline. The pages call the same API endpoints as any client, so the API key rule still applies.
"""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent / "static"

router = APIRouter(include_in_schema=False)


@router.get("/")
def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/try")
def playground() -> FileResponse:
    return FileResponse(STATIC_DIR / "try.html")


def mount_web(app: FastAPI) -> None:
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
