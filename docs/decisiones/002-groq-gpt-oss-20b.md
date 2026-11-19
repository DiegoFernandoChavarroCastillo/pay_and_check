# ADR-002 · Groq con `openai/gpt-oss-20b`

- **Estado:** aceptada
- **Fecha:** 2026-11-18
- **Fuente:** `docs/planFinal.md` §4.3 (N-20)

## Contexto

La app usa un modelo de lenguaje para siete tareas (`TAREAS` en
[`backend/app/services/ia_uso.py`](../../backend/app/services/ia_uso.py)): extraer un gasto de texto, voz o SMS
(`registro`), de un recibo (`recibo`), reaccionar a un gasto, consejos del día, chat, reporte semanal y
*wrapped*. El costo por llamada importa (planes con cupo, [ADR-008](008-planes-simulados-cupo-ia.md)) y la
latencia también: la persona espera la respuesta.

El plan original fijaba `llama-3.1-8b-instant` en Groq.

## Decisión

- Proveedor: **Groq**, con su SDK oficial (`groq` en [`backend/pyproject.toml`](../../backend/pyproject.toml)).
- Modelo: **`openai/gpt-oss-20b`** (constante `MODEL` en
  [`backend/app/services/groq_client.py`](../../backend/app/services/groq_client.py)).
- Un solo punto de salida hacia Groq: `_chat()` en `groq_client.py`. Ahí viven el *timeout*, el registro de uso y
  el *gate* de cupo.
- Parámetros por tarea, no modelos por tarea:

  | Tarea | Modelo | `reasoning_effort` | `temperature` |
  |---|---|---|---|
  | Extracción (texto, recibo) | `MODEL` | `low` (por defecto de `_chat`) | 0 |
  | Reporte semanal | `MODEL` | `low` | 0.4 |
  | Coach en texto (reacción, chat, *wrapped*) | `COACH_MODEL` | `COACH_REASONING = "medium"` | 0.6 |
  | Coach en JSON (consejos) | `COACH_MODEL` | `medium` | 0.5 |

## Por qué se descartó Llama 3.1 8B y qué se probó

Lo único que el repo registra es el comentario sobre `MODEL` en `groq_client.py`:

- Groq **descontinuó** `llama-3.1-8b-instant`: devolvía `404 model_not_found` al probarlo en septiembre de 2026.
  No fue una comparación de calidad; el modelo dejó de existir.
- De los modelos de propósito general disponibles en la cuenta, `gpt-oss-20b` era el más chico y barato, y
  respondió bien al prompt de extracción en español **al probarlo a mano**.
- Con `reasoning_effort="low"` el coach se limitaba a copiar el dato en vez de redactar el consejo; por eso el
  coach va en `medium` (comentario sobre `COACH_REASONING`).
- El modo JSON de Groq (`response_format={"type": "json_object"}`) se descartó: con gpt-oss devolvía vacío de
  forma intermitente (`400 json_validate_failed`). El JSON se pide en el prompt y se extrae con `_extraer_json`
  (comentario en `_chat`).

**No hay en el repo** una batería comparativa de modelos, métricas de precisión ni un registro de las pruebas
manuales. Si se quiere afirmar algo más que lo anterior, hay que hacer y versionar esa prueba.

## Sobre "modelo único por tarea"

`planFinal.md` habla de "modelo único por tarea". En el código **hoy hay un solo modelo para todas las tareas**:
`COACH_MODEL = MODEL`. La separación existe como constante para poder subir el coach a uno más capaz (el
comentario sugiere `openai/gpt-oss-120b`) sin encarecer la extracción, pero no está en uso.

## Alternativas consideradas

- **`gpt-oss-120b` para todo.** Más capaz, más caro y lento. Queda como opción solo para `COACH_MODEL`.
- **Otro proveedor (OpenAI, Anthropic, Gemini).** No está evaluado en el repo. El cambio quedaría acotado a
  `groq_client.py`, que es el único módulo que importa el SDK.
- **Modelo en el teléfono.** No se evaluó. Voz y OCR sí corren en el teléfono y no llegan como audio ni imagen al
  backend (solo texto: `texto` y `texto_ocr` en [`routers/expenses.py`](../../backend/app/routers/expenses.py)).

## Consecuencias

- Cambiar de modelo es cambiar una constante; cambiar de proveedor, un archivo.
- Sin reintentos (`GROQ_MAX_REINTENTOS = 0`) y con `GROQ_TIMEOUT_S = 15`: si Groq falla, la persona recibe el
  respaldo en segundos ([ADR-003](003-ia-redacta-no-calcula.md)).
- Sin `GROQ_API_KEY` el backend arranca igual: el parseo responde 503 y el coach usa sus textos de respaldo
  ([`core/config.py`](../../backend/app/core/config.py)).
- El límite de tokens por minuto de Groq es el primer cuello de botella al crecer
  ([ADR-001](001-monolito-modular.md)).
