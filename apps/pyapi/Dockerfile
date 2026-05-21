FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY apps/pyapi/pyproject.toml ./
RUN pip install --no-cache-dir fastapi>=0.124.0 "uvicorn[standard]>=0.38.0" httpx>=0.28.0

COPY apps/pyapi/pyapi ./pyapi

RUN useradd --create-home --uid 1000 careerpilot && \
    mkdir -p /data && chown -R careerpilot:careerpilot /data /app
USER careerpilot

ENV APP_ADDR=:8080 \
    DATABASE_URL=postgresql://careerpilot:careerpilot@postgres:5432/careerpilot

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "pyapi.main:app", "--host", "0.0.0.0", "--port", "8080"]
