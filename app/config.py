"""Settings from environment variables (and an optional .env file). See .env.example."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Service ---
    log_level: str = "INFO"
    max_upload_mb: int = 10  # per file; bigger files get 413

    # --- Tesseract ---
    tessdata_dir: str = "models/tessdata"  # folder with tgk/eng/ocrb .traineddata; /models/tessdata in Docker
    tesseract_cmd: str | None = None  # path to the tesseract binary if it is not on PATH
    tesseract_lang: str = "tgk"  # language of /ocr; "tgk+rus" for mixed text
    tesseract_psm: int = 3  # page segmentation of /ocr: 3 = auto layout, 6 = one block of text
    ocr_threads: int = 2  # parallel Tesseract processes per passport request; ~ number of CPU cores

    # --- /ocr preprocessing defaults (can be overridden per request) ---
    ocr_flatten: bool = True  # even out uneven lighting / shadows
    ocr_deskew: bool = True  # straighten text rotated up to 15 degrees
    ocr_min_score: float = 0.0  # drop lines with confidence below this (0..1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
