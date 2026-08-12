# syntax=docker/dockerfile:1
#
# Imagen de PRODUCCION de @ambienta/api (FastAPI). Usuario no-root, sin reload.
# El contexto de build es la RAIZ del repo (context: . en el compose).

FROM python:3.12-slim
WORKDIR /repo/apps/api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app

# Usuario sin privilegios: si el proceso se ve comprometido, no corre como root.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /repo
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
