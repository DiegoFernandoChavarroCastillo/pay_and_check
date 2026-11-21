# ADR-008 · Planes simulados en el piloto y cupo de IA por plan

- **Estado:** aceptada
- **Fecha:** 2026-11-18

## Contexto

El modelo de negocio (`docs/negocio/`) define cuatro planes y el costo de IA es el principal costo variable. El
piloto se distribuye por APK ([ADR-007](007-distribucion-apk.md)), así que no hay Google Play Billing, y
integrar una pasarela de pago no cabe en los tiempos.

## Decisión

- **Catálogo en código**, `CATALOGO` en [`backend/app/services/planes.py`](../../backend/app/services/planes.py):

  | Plan | Precio COP (IVA incl.) | Cupo IA/mes | Estado en el piloto |
  |---|---|---|---|
  | `gratis` | 0 | 50 | real |
  | `institucional` | 4.998 por estudiante | 300 | se activa con código de convenio |
  | `premium` | 9.990 | 300 | simulado |
  | `familiar` | 19.990, hasta 3 | 390 compartidas | simulado |

- **Cobro simulado (D1):** `PUT /me/subscription` cambia el plan sin cobrar y la respuesta lleva
  `aviso = "Plan simulado: en el piloto no hay cobro real."` ([`routers/plans.py`](../../backend/app/routers/plans.py)).
  Institucional no se pide: solo se activa canjeando un código de convenio (`POST /me/subscription/redeem`).
- **Sin fila de suscripción = Gratis** (`plan_de` en `planes.py`).
- **El cupo sale del plan** (`cupo_de` en [`services/ia_uso.py`](../../backend/app/services/ia_uso.py)). En
  Familiar se comparte entre los integrantes del grupo (`_quienes_comparten`).
- **Un solo punto de control:** `_chat()` en [`groq_client.py`](../../backend/app/services/groq_client.py)
  revisa el cupo antes de llamar a Groq y registra cada llamada en `ai_usage`. Si no hay cupo, registra
  `bloqueado_por="cupo"` y lanza `CupoIAAgotado`, que es un `GroqServiceError`: cada llamador ya sabe responder
  con su respaldo. El parseo responde **402**; el coach contesta con el texto `sin_cupo`.
- **Solo cuentan las llamadas exitosas** (`_contar` filtra `AiUsage.exito`); lo servido desde caché no llama a
  Groq y no deja fila.
- El mes se calcula con `today_for(user)` ([ADR-005](005-zona-horaria-del-usuario.md)) y no hay *cron* de
  reinicio ([ADR-004](004-sin-colas-ni-cron.md)).

## Cómo se enchufaría Google Play Billing

Queda registrado cómo se agregaría: la app compra con Google Play Billing, el backend
**verifica el recibo** de la compra contra Google y, si es válido, aplica el mismo cambio que hoy hace
`PUT /me/subscription`. **Nada de esto está implementado**: no hay verificación de recibos, *webhooks* de
Google ni campos de vencimiento o renovación en `subscriptions`
([`models/plan.py`](../../backend/app/models/plan.py)). Hoy una suscripción no vence.

## Alternativas consideradas

- **Pasarela real (Wompi, Mercado Pago, Stripe).** Fuera del alcance del piloto (D1).
- **Sin planes, cupo fijo para todos.** Descartado: el modelo financiero depende de diferenciar planes.
- **Catálogo en base de datos.** Descartado por ahora: cambia poco y en código se prueba con más facilidad.

## Consecuencias

- El piloto permite recorrer el flujo completo de planes, cupo y familia sin mover dinero.
- Cualquiera puede ponerse Premium gratis en el piloto: el cupo de 300 no protege el costo hasta que haya cobro.
- El cupo Gratis empezó en 50 y **subió a 150** el 18 nov 2026: con una reacción del coach por gasto, 50 se
  agotaban en la primera semana. El modelo financiero ya lo refleja (D2 en `docs/planes.md`).
- La revisión del cupo y el registro no son atómicos: llamadas simultáneas pueden pasarse por unas pocas.
- Pruebas: [`tests/test_planes_modelo.py`](../../backend/tests/test_planes_modelo.py),
  [`tests/test_planes_api.py`](../../backend/tests/test_planes_api.py),
  [`tests/test_planes_cupo.py`](../../backend/tests/test_planes_cupo.py),
  [`tests/test_ia_uso.py`](../../backend/tests/test_ia_uso.py).
