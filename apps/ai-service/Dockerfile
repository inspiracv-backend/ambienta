# AI Service de Ambienta (SPEC-09).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MIGRACIONES_DIR=/app/migraciones

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[openai,anthropic]"
COPY migraciones ./migraciones
COPY evaluacion ./evaluacion

RUN useradd --create-home --uid 10001 ia
USER ia

EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/salud', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "ambienta_ia.api.app:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers"]
