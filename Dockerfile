# Backend image: the API (uvicorn) and the worker (arq) run from the same image.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HF_HUB_DISABLE_TELEMETRY=1 \
    DATA_DIR=/app/data/kb

RUN useradd -m -u 1000 app && mkdir -p /opt/fastembed /app/data/kb && chown -R app /opt/fastembed /app

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

USER app

# Bake the embedding model into the image so the first answer isn't a ~470 MB download.
COPY --chown=app rag/ rag/
ARG EMBED_MODEL=intfloat/multilingual-e5-small
RUN EMBED_MODEL=$EMBED_MODEL python -c "from rag.embed import model; model()"

COPY --chown=app . .

EXPOSE 8000
CMD ["sh", "scripts/start_api.sh"]
