# The base can be changed for compatibility checks (CI builds it on Debian 12, as the TUU VPS).
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

# LibreOffice (MPL) without a desktop: PDF of the exported pieces and the fidelity check (Phase 6)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libreoffice-writer-nogui libreoffice-calc-nogui fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install .
COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --create-home --uid 10001 maestro
USER maestro

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
