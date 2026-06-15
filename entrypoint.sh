#!/bin/sh
set -e

UPLOADS_DIR="/app/app/static/uploads"
UPLOADS_SEED="/app/app/static/uploads_seed"
DB_PATH="/app/instance/investmap.db"
DB_SEED="/app/instance_seed/investmap.db"

# Скопировать seed-картинки если volume пустой
if [ -d "$UPLOADS_SEED" ]; then
    count=$(find "$UPLOADS_DIR" -maxdepth 1 -type f 2>/dev/null | wc -l)
    if [ "$count" -eq 0 ]; then
        echo "[entrypoint] Seeding uploads..."
        cp -r "$UPLOADS_SEED/." "$UPLOADS_DIR/"
    fi
fi

# Скопировать seed-БД если volume пустой
if [ -f "$DB_SEED" ] && [ ! -f "$DB_PATH" ]; then
    echo "[entrypoint] Seeding database..."
    mkdir -p /app/instance
    cp "$DB_SEED" "$DB_PATH"
fi

exec "$@"
