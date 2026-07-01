FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ── dependencies ──────────────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install .

# ── final image ───────────────────────────────────────────────────────────
FROM deps AS runtime
RUN apt-get update -qq && apt-get install -y -qq curl ca-certificates && \
    curl -sS https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /app/global-bundle.pem && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
COPY src/ ./src/

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
