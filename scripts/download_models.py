"""Download Tesseract models into models/tessdata: uv run python scripts/download_models.py

tgk, eng - tessdata_best (official, Apache-2.0)
ocrb     - OCR-B font model for MRZ, github.com/Shreeshrii/tessdata_ocrb
"""

import sys
import urllib.request
from pathlib import Path

MODELS = {
    "tgk": "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/tgk.traineddata",
    "eng": "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata",
    "ocrb": "https://raw.githubusercontent.com/Shreeshrii/tessdata_ocrb/master/ocrb.traineddata",
}
DEST = Path(__file__).resolve().parent.parent / "models" / "tessdata"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    force = "--force" in sys.argv
    for name, url in MODELS.items():
        path = DEST / f"{name}.traineddata"
        if path.exists() and not force:
            print(f"{name}: уже есть")
            continue
        print(f"{name}: скачиваю {url}")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
        print(f"{name}: {path.stat().st_size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
