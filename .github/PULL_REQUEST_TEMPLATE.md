## Ticket

PS-<!-- número -->

## Qué cambia

<!-- Una o dos frases: el problema y cómo queda resuelto. -->

## Cómo se probó

- [ ] Backend: `cd backend && uv run ruff check . && uv run pytest`
- [ ] App: `cd mobile && flutter analyze && flutter test`
- [ ] Probado a mano: <!-- qué pantalla o endpoint, con qué datos -->

## Checklist

- [ ] El título del PR empieza con el ID del ticket (`PS-xx: ...`).
- [ ] Si hay migración nueva, `uv run alembic upgrade head` corre sobre una base limpia.
- [ ] Si cambia el texto de la política de privacidad, se subió la versión en la app y en el backend.
