FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    OCR_LANG=por+eng \
    UPLOAD_DIR=/data/private_uploads

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /data/private_uploads \
    && chown -R app:app /data/private_uploads

COPY requirements.lock ./
RUN python -m pip install -r requirements.lock && python -m pip check
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/__init__.py scripts/ci_database.py scripts/migrate_production.py scripts/start_api.py ./scripts/

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
    CMD python -c "import json,os,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health',timeout=3); assert r.status==200 and json.load(r)=={'status':'ok'}"
CMD ["python", "-m", "scripts.start_api"]
