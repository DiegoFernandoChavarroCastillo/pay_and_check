#!/bin/sh
# Arranque en producción: aplica las migraciones pendientes, siembra las categorías por defecto (ambos pasos
# son idempotentes) y levanta la API en el puerto que asigne la plataforma (PORT), o en el 8000.
set -e
alembic upgrade head
python -m app.db.seed
# --proxy-headers / --forwarded-allow-ips: detrás del proxy de Render, la IP del cliente viene en
# X-Forwarded-For; sin esto el límite de intentos de login vería la IP del proxy, la misma para todos.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
