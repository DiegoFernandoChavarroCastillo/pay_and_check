# --- Etapa 1: build de dependencias ---
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

# Solo los manifiestos primero: cachea la capa de dependencias entre builds
# mientras no cambien pyproject.toml / uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev


# --- Etapa 2: imagen final liviana ---
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# Solo el venv ya resuelto y el código — nada de uv, caché de pip, ni
# archivos de build que no hacen falta en producción.
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app
COPY --from=builder --chown=appuser:appuser /app/alembic /app/alembic
COPY --from=builder --chown=appuser:appuser /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=appuser:appuser /app/start.sh /app/start.sh

ENV PATH="/app/.venv/bin:$PATH"
USER appuser

EXPOSE 8000

# Migra, siembra y arranca. El comando vive en un script y no en la configuración de la plataforma: Render
# no interpreta las comillas de un `sh -c "..."` puesto como comando y el contenedor moría al arrancar.
CMD ["sh", "/app/start.sh"]
