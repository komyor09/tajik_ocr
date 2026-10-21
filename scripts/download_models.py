"""Download the Tesseract models the service needs.

    python scripts/download_models.py [folder]     # default: $TESSDATA_DIR or models/tessdata

In Docker the folder is the /models volume, see DEPLOY.md.

tgk, eng - tessdata_best (official, Apache-2.0)
ocrb     - OCR-B font model for MRZ, github.com/Shreeshrii/tessdata_ocrb
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "tgk": "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/tgk.traineddata",
    "eng": "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata",
    "ocrb": "https://raw.githubusercontent.com/Shreeshrii/tessdata_ocrb/master/ocrb.traineddata",
}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dest = Path(args[0] if args else os.getenv("TESSDATA_DIR", "models/tessdata"))
    force = "--force" in sys.argv
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        path = dest / f"{name}.traineddata"
        if path.exists() and not force:
            print(f"{name}: уже есть ({path})")
            continue
        print(f"{name}: скачиваю {url}")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
        print(f"{name}: {path.stat().st_size / 1e6:.1f} МБ -> {path}")


if __name__ == "__main__":
    main()
