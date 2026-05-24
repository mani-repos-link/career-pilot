FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    libjpeg62-turbo \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/pyapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium && \
    chmod -R a+rx /ms-playwright

COPY apps/pyapi/pyapi ./pyapi
COPY config ./config
COPY migrations ./migrations

RUN useradd --create-home --uid 1000 careerpilot && \
    mkdir -p /data /app/data && chown -R careerpilot:careerpilot /data /app
USER careerpilot

ENV APP_ADDR=:8080 \
    DATABASE_URL=postgresql://careerpilot:careerpilot@postgres:5432/careerpilot

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "pyapi.main:app", "--host", "0.0.0.0", "--port", "8080"]
