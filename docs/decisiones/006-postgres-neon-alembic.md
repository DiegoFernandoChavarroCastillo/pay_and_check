# ADR-006 · PostgreSQL en Neon y migraciones con Alembic

- **Estado:** aceptada
- **Fecha:** 2026-11-18
- **Fuente:** `docs/planFinal.md` §4.3 (N-20)

## Contexto

Los datos son relacionales (usuarios, presupuestos, categorías, gastos, metas, planes, grupos) y necesitan
transacciones e integridad referencial. El piloto no tiene presupuesto para infraestructura y el backend en Render
no trae una base persistente en el plan gratuito.

## Decisión

- **PostgreSQL** como base, con **SQLModel** (SQLAlchemy) como ORM y `psycopg2-binary` como driver
  ([`backend/pyproject.toml`](../../backend/pyproject.toml)).
- **Neon** en producción, como base externa: [`render.yaml`](../../render.yaml) dice que la cadena de conexión
  de Neon se pega en `DATABASE_URL`, y el servicio va en la región `ohio` porque la base está en AWS `us-east-2`
  ("cada petición hace varias consultas"). En local, Postgres 16 en Docker
  ([`backend/docker-compose.yml`](../../backend/docker-compose.yml)).
- **Alembic** para el esquema: `backend/alembic/versions/` tiene 11 migraciones;
  [`alembic/env.py`](../../backend/alembic/env.py) toma la URL de `settings` y los modelos de
  `app.models`. Producción migra al arrancar (`alembic upgrade head` en
  [`backend/start.sh`](../../backend/start.sh)).
- El engine usa `pool_pre_ping=True` y `pool_recycle=300` porque Neon cierra conexiones inactivas y suspende la
  base; sin eso la primera petición tras la suspensión daba 500
  ([`backend/app/db/session.py`](../../backend/app/db/session.py)).

## Alternativas consideradas

- **Base gestionada de Render.** Viable; se eligió Neon (la razón concreta no está registrada en el repo más allá
  de que el README lo describe como "el camino previsto").
- **SQLite en producción.** Descartado: el disco del contenedor de Render no es persistente.
- **`SQLModel.metadata.create_all` sin migraciones.** Descartado: no permite evolucionar el esquema con datos.
- **NoSQL.** Descartado: el dominio es relacional.

## Consecuencias

- Las pruebas usan **SQLite en memoria**, no Postgres ([`tests/conftest.py`](../../backend/tests/conftest.py)):
  son herméticas y rápidas en CI, pero no detectan diferencias de dialecto (tipos, restricciones,
  comportamiento de `func`). Las migraciones de Alembic no se ejecutan en CI
  ([`.github/workflows/backend-ci.yml`](../../.github/workflows/backend-ci.yml)).
- Cada despliegue aplica migraciones antes de arrancar: una migración que falla tumba el arranque.
- La suspensión de Neon en el plan gratuito agrega latencia a la primera petición tras inactividad.
- No hay *pooler* configurado en el código ni réplica de lectura; es la fase C del plan
  ([ADR-001](001-monolito-modular.md)).
