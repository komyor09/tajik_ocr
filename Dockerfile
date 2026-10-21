# Tajik OCR API — internal API service (Tesseract, CPU only)
#
#   docker build -t tajik-ocr .
#   docker run -d -p 8000:8000 -v /srv/models:/models:ro --env-file .env tajik-ocr
#
# Tesseract models are NOT in the image: they are read from the /models volume (see DEPLOY.md).

# ---------- stage 1: Python dependencies ----------
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
# requirements.txt first: this layer is rebuilt only when dependencies change, not on code edits
COPY requirements.txt .
RUN /opt/venv/bin/pip install -r requirements.txt


# ---------- stage 2: runtime ----------
FROM python:3.12-slim

# Only the Tesseract binary; its language packs from apt are not used (models come from /models)
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

# OMP_THREAD_LIMIT=1: the passport reader already runs OCR_THREADS Tesseract processes in parallel,
# extra OpenMP threads inside each process only fight for the same 2 cores.
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_THREAD_LIMIT=1 \
    TESSDATA_DIR=/models/tessdata

RUN useradd --system --uid 10001 --no-create-home app

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY scripts/download_models.py scripts/download_models.py
COPY app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
