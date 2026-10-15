# Tajik OCR API — production image (Tesseract engine only, without PaddleOCR)
#
#   docker compose up -d --build
#
# Debian trixie ships Tesseract 5.5 (same major version as the Windows dev setup).

# ---------- stage 1: Python dependencies + Tesseract models ----------
FROM python:3.12-slim-trixie AS build

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
# On a server OpenCV needs no GUI: the headless build has the same cv2 API without libGL/Qt
RUN python -m venv /opt/venv \
 && grep -v '^opencv-contrib-python' requirements.txt > requirements.docker.txt \
 && /opt/venv/bin/pip install -r requirements.docker.txt opencv-contrib-python-headless==4.10.0.84

# Models are gitignored, so they are downloaded at build time (tgk, eng, ocrb ≈ 31 MB)
COPY scripts/download_models.py scripts/download_models.py
RUN python scripts/download_models.py


# ---------- stage 2: runtime ----------
FROM python:3.12-slim-trixie

# Only the Tesseract binary: the models come from the project, not from apt
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

# OMP_THREAD_LIMIT=1: the passport reader already runs several Tesseract processes in parallel,
#   extra OpenMP threads per process only fight for the same cores.
# WEB_CONCURRENCY: number of uvicorn worker processes (override in docker-compose / .env).
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_THREAD_LIMIT=1 \
    WEB_CONCURRENCY=1

RUN useradd --system --uid 10001 --home-dir /app ocr

# WORKDIR matters: app/tess.py passes models/tessdata to Tesseract as a relative path
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /build/models ./models
COPY app ./app

USER ocr
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "10"]
