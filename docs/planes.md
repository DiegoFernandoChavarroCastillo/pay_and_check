# Planes y cupo de IA

> Fuente: `docs/planFinal.md` §3.1 y §4.2, y el modelo financiero de `docs/negocio/`. Este documento es la
> referencia de qué incluye cada plan y qué cuenta como una "solicitud" de IA. Lo que el código aplica sale de
> aquí (`backend/app/services/planes.py`).

## 1. Decisiones tomadas

| # | Decisión | Qué significa |
|---|---|---|
| D1 | **Cobro simulado** | En el piloto no hay pasarela de pago. Cambiar a Premium o Familiar solo cambia el plan y el cupo, y la app avisa que no hay cobro real. Google Play Billing queda fuera del alcance (la demo es por APK). |
| D2 | **El plan Gratis incluye 50 solicitudes de IA al mes** | El modelo financiero cuenta "usuarios gratis" en el costo de IA pero nunca fijaba su cupo. **Por validar** con el modelo. |
| D3 | **Familiar: 390 solicitudes compartidas** por cuenta familiar, hasta 3 integrantes | Se simula con un solo grupo. |
| — | **La cuenta nueva nace en Gratis** | "Sin suscripción" equivale a Gratis: no hay fila hasta que la persona cambia de plan. |
| — | **El código de convenio activa Institucional** | La universidad paga; la persona canjea el código que le entregan. |

## 2. Los planes

Precios en pesos colombianos, con IVA.

| Plan | Quién paga | Precio | Cupo de IA al mes | Cómo se activa | Estado en el piloto |
|---|---|---|---|---|---|
| **Gratis** | nadie | $0 | **50** | Es el plan de toda cuenta nueva | Real |
| **Institucional** | la universidad | $4.998 por estudiante activo | **300** por persona | Canjeando un **código de convenio** (ej. ECI) | Real, por código |
| **Premium** | la persona | $9.990 | **300** por persona | `PUT /me/subscription` | Simulado, sin cobro |
| **Familiar** | la familia | $19.990 (hasta 3 jóvenes) | **390 compartidas** | `PUT /me/subscription` crea la familia y da un **código familiar** que los demás canjean | Simulado, sin cobro |

## 3. Qué cuenta como una "solicitud"

Una solicitud es **cada llamada exitosa a Groq**. Las seis interacciones del inventario del modelo financiero
(hoja `Costo_IA`) son siete tareas en la tabla `ai_usage`, porque el registro por texto y el de recibo son dos
tareas del mismo tipo de interacción:

| Interacción del modelo | Tarea en `ai_usage` | Endpoint |
|---|---|---|
| Registro de un movimiento (texto, voz, SMS) | `registro` | `POST /expenses/parse`, `POST /expenses/from-text` |
| Registro con foto de recibo | `recibo` | `POST /expenses/parse-receipt` |
| Reacción tras un gasto | `reaccion` | `POST /coach/reaction` |
| Consejos del día | `consejos` | `GET /coach/insights` |
| Chat con el coach | `chat` | `POST /coach/chat` |
| Reporte semanal | `reporte` | `GET /reports/weekly` |
| *Wrapped* mensual | `wrapped` | `GET /reports/monthly-wrapped` |

**Cuentan**
- Cada llamada que Groq respondió, aunque el resultado se descarte después (un guardrail, un tema ajeno, un
  texto que no daba un gasto).
- El reintento del chat cuando la respuesta traía cifras inventadas: es una segunda llamada.

**No cuentan**
- Lo servido desde **caché**: los consejos del día se calculan una vez al día por tono e idioma.
- La **voz** y el **OCR** de recibos, que corren en el teléfono sin IA de pago.
- Las llamadas que **fallaron** (Groq caído o con límite de velocidad).
- Las llamadas **bloqueadas por cupo**: no llegan a Groq.
- El registro manual, los gastos fijos, las metas y todo lo que no usa IA.

## 4. Reinicio, cupo compartido y cuando se agota

- **Reinicio:** el día 1 de cada mes a las 00:00 **en la zona horaria de la persona** (no la del servidor). No hay
  un *cron*: cada llamada queda marcada con su mes y el contador es `WHERE mes = <mes actual de la persona>`.
- **Familiar compartido:** las 390 solicitudes se reparten entre todos los integrantes de la familia; la suma de
  lo que usó cada uno no puede pasar de 390.
- **Al agotarse el cupo**, la IA no se llama y cada función usa su texto de respaldo:
  - el chat responde un texto fijo con la situación de la persona;
  - la reacción, los consejos, el reporte semanal y el *wrapped* usan su texto determinista;
  - el registro por texto o recibo responde **402** y la app lleva al formulario manual, que no usa IA.
- La revisión del tope y el registro de la llamada no son atómicos: dos peticiones simultáneas de una misma
  persona pueden pasarse del tope por unas pocas llamadas. Es un tope de costo, no un límite de seguridad.

## 5. Cómo cambia una persona de plan

| Desde → hacia | Cómo | Efecto |
|---|---|---|
| Cualquiera → **Gratis** | `PUT /me/subscription` con `gratis` | Pierde el plan de pago. |
| Gratis → **Premium** | `PUT /me/subscription` con `premium` | Simulado. |
| Gratis → **Familiar** | `PUT /me/subscription` con `familiar` | Se crea la familia, la persona queda como **titular** y recibe un código familiar. |
| Gratis → **Institucional** | `POST /me/subscription/redeem` con un código de convenio | El código debe existir, no estar vencido ni agotado (`max_usos`). Un código inexistente da 404; vencido o agotado, 422. |
| Gratis → **integrante de una familia** | `POST /me/subscription/redeem` con el código familiar | Máximo 3 integrantes contando al titular. |

Institucional **solo** se activa con un código de convenio: `PUT` lo rechaza.

**La familia**
- Quien activó Familiar es el **titular**. Si el titular vuelve a Gratis, cambia de plan (Premium, o canjea un
  convenio) o **borra su cuenta**, la familia se **disuelve**: todos sus integrantes vuelven a Gratis y el código
  familiar deja de servir.
- Si un **integrante** (no titular) pide Premium o Gratis, canjea un convenio o borra su cuenta, **sale** de la
  familia; los demás siguen.
- Un integrante no puede pedir Familiar mientras esté en una familia: primero debe salir.

## 6. Convenios

No hay un endpoint para crear convenios: no existe el rol de administrador. Se crean con un script (y, más
adelante, con la semilla de demostración, PS-35):

```
uv run python -m app.db.crear_convenio --org ECI --codigo ECI-2026 --vence 2026-12-31 --max-usos 460
```

Crea la organización si no existe. `--vence` y `--max-usos` son opcionales (sin ellos, el código no vence ni
tiene tope de usos). El código se guarda en mayúsculas y al canjear no distingue mayúsculas.

## 7. Pendiente fuera del código

- Reflejar el cupo gratis (50) en las hojas `Costo_IA` e `Inputs` del modelo financiero (PS-52).
- Cuando haya datos medidos de `ai_usage` (`uv run python -m app.db.reporte_ia`), reemplazar el factor de
  incertidumbre del costo por solicitud por el promedio real.
