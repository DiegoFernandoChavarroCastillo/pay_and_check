# ADR-011 · Backend de producción en AWS EC2, Render como respaldo

- **Estado:** aceptada
- **Fecha:** 2026-11-20
- **Reemplaza en parte:** el camino «Render + Neon» de [setup.md](../setup.md#desplegar) como backend principal

## Contexto

El backend corría en Render, plan free ([ADR-006](006-postgres-neon-alembic.md), `render.yaml`). El plan
gratuito duerme el servicio tras unos 15 minutos sin tráfico: la primera petición tardó 52,5 s (medido el 20 nov
2026), y la tarea `keep-alive.yml` solo lo mitiga. Para el piloto y la presentación el equipo quería un servidor
encendido todo el tiempo y bajo su control.

## Decisión

- La API de `main` corre en una **instancia AWS EC2**, detrás de **Caddy**, que da HTTPS con certificado
  automático en `https://paycheck-swnt.duckdns.org` (DuckDNS como dominio gratuito).
- La base de datos sigue en **Neon** y las migraciones se aplican al arrancar (`backend/start.sh`).
- GitHub apunta los clientes a AWS: `API_BASE_URL` (APK) y `WEB_API_BASE_URL` (web).
- Render queda como **respaldo**: mismo código y misma base, pero dormido.

## Alternativas consideradas

- **Render Starter (US$7 al mes).** Nunca duerme y no exige administrar un servidor. Sigue siendo el camino más
  simple si nadie puede mantener la instancia.
- **Seguir en Render free con `keep-alive`.** Gratis, pero depende de que GitHub corra el cron a tiempo.

## Consecuencias

- **La instancia la administra una persona del equipo**: actualizar el código, reiniciar y cambiar variables
  (`CORS_ORIGINS`, `GOOGLE_CLIENT_ID`) es manual. No hay despliegue automático del backend.
- La instalación de la instancia no está documentada en el repo (pendiente en [pendientes.md](../pendientes.md)).
- DuckDNS y la IP de la instancia son puntos de falla: si la instancia cambia de IP o se detiene, la app y la web
  dejan de funcionar hasta actualizar el DNS o cambiar a Render.
- `keep-alive.yml` llama a `API_BASE_URL`, así que ahora mantiene despierto a AWS (inofensivo) y no a Render.
- Cambiar de backend exige recompilar el APK (la URL se fija al compilar, [ADR-007](007-distribucion-apk.md)) y
  volver a publicar la web.
