# ---- build stage ----
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps (for email-validator, python-slugify, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install gunicorn==22.0.0


# ---- runtime stage ----
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Seed-данные — entrypoint копирует их в volumes при первом старте
RUN cp -r app/static/uploads app/static/uploads_seed \
    && cp -r instance instance_seed \
    && mkdir -p instance app/static/uploads

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_DEBUG=false

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "--preload", "run:app"]
