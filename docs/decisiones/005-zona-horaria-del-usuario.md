# ADR-005 · El "hoy" es el de la persona, no el del servidor

- **Estado:** aceptada
- **Fecha:** 2026-11-18
- **Fuente:** `docs/planFinal.md` §4.3 (N-20)

## Contexto

El servidor corre en UTC (Render). En Colombia (UTC−5), a las 7 p. m. el servidor ya está en el día siguiente.
Con `date.today()`, un gasto de la noche caería en el día equivocado, la racha se rompería y el cupo de IA se
reiniciaría cinco horas antes del cambio de mes.

## Decisión

- Cada persona tiene `zona_horaria` (nombre IANA, por defecto `America/Bogota`) en
  [`backend/app/models/user.py`](../../backend/app/models/user.py), validada con `ZoneInfo` en
  [`schemas/user.py`](../../backend/app/schemas/user.py).
- La app la lee del teléfono con `FlutterTimezone.getLocalTimezone()` al cargar la sesión y, si difiere de la
  guardada, la actualiza con `updateMe({'zona_horaria': …})`
  ([`mobile/lib/data/session.dart`](../../mobile/lib/data/session.dart), `_conZonaHorariaDelTelefono`).
- El backend usa `today_for(user)` ([`backend/app/core/time.py`](../../backend/app/core/time.py)) en lugar de
  `date.today()`. Lo usan los routers de presupuestos, check-ins, coach, gastos, gamificación, metas, planes,
  gastos fijos y reportes, además de `budget_lookup.py` e `ia_uso.py` (el mes del cupo).
- Verificado: no queda ningún `date.today()` ni `datetime.now()` sin zona en `backend/app/`; la única mención es
  el docstring de `today_for`. Las marcas de tiempo (`created_at`) van en UTC con `utcnow()`.

## Alternativas consideradas

- **Zona fija `America/Bogota` en el servidor.** Más simple, pero falla con cualquier persona fuera de Colombia
  y ata el código a una sola región.
- **Que la app mande la fecha en cada petición.** Descartado: el cliente decide el día y puede hacer trampa con
  rachas, retos y cupo.

## Consecuencias

- Fechas, rachas, retos, gastos fijos y el mes del cupo son coherentes con el reloj de la persona.
- `reinicia_el` del cupo es el primer día del mes siguiente en su zona
  ([`routers/plans.py`](../../backend/app/routers/plans.py)).
- Las pruebas fijan el reloj local con un *fixture* (`reloj_local` en
  [`tests/conftest.py`](../../backend/tests/conftest.py)) y hay pruebas específicas en
  [`tests/test_zona_horaria.py`](../../backend/tests/test_zona_horaria.py).
- Si la persona viaja, su "hoy" cambia cuando la app actualiza la zona; un día puede quedar más corto o más largo.
