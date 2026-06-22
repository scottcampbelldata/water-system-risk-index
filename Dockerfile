# Reproducible image for the Water System Risk Index API.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install pinned dependencies first for layer caching.
COPY requirements-api.lock.txt ./
RUN pip install --no-cache-dir -r requirements-api.lock.txt

# Application code and the data seeds the loader needs.
COPY waterapi ./waterapi
COPY data/processed/app_data.json data/processed/boundaries.json data/processed/swap_areas.json ./data/processed/

EXPOSE 8000

# init-db + load are run once (see docker-compose); this serves the API.
CMD ["python", "-m", "uvicorn", "waterapi.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
