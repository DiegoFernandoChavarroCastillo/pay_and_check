#!/bin/sh
# Arranque en producción: aplica las migraciones pendientes, siembra las categorías por defecto (ambos pasos
# son idempotentes) y levanta la API en el puerto que asigne la plataforma (PORT), o en el 8000.
set -e
alembic upgrade head
python -m app.db.seed
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
