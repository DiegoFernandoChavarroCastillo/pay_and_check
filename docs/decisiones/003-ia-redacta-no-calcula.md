# ADR-003 · La IA redacta, no calcula

- **Estado:** aceptada
- **Fecha:** 2026-11-18
- **Fuente:** `docs/planFinal.md` §4.3 (N-20)

## Contexto

Un modelo de lenguaje suma mal, inventa cifras y puede fallar o no responder. En una app de finanzas, un
"te quedan $X por día" equivocado es peor que no decir nada. Además Groq puede estar caído, limitado o sin cupo.

## Decisión

1. **Todo número sale de código determinista.** El disponible, el disponible por día, los días restantes, lo
   gastado y lo apartado salen de `summary_for` en
   [`backend/app/services/budget_totals.py`](../../backend/app/services/budget_totals.py) y
   [`budget_calculator.py`](../../backend/app/services/budget_calculator.py); los patrones, de
   [`patterns.py`](../../backend/app/services/patterns.py). La IA recibe esas cifras ya calculadas en texto
   (`contexto_financiero` en [`services/coach.py`](../../backend/app/services/coach.py)) y solo las redacta.
2. **Guardrails sobre la salida** (`coach.py`):
   - `inventa_cifras`: descarta un mensaje con cifras de dos o más dígitos que no estén en el dato de partida.
     En el chat no se descarta sin más: se le pide al modelo **una vez** que repita sin cifras nuevas, salvo que
     la persona misma haya escrito números (`responder_chat`).
   - `rompe_guardrails`: lenguaje culposo, asesoría de inversión regulada y los filtros de salida de
     [`ia_seguridad.py`](../../backend/app/services/ia_seguridad.py) (fuga del prompt, URLs, código/HTML, más de
     1.200 caracteres).
3. **Texto de respaldo determinista** para cada salida (`_RESPALDO` en `coach.py`, `resumen_de_respaldo` en
   [`weekly_report.py`](../../backend/app/services/weekly_report.py), `_CIERRE` en
   [`wrapped.py`](../../backend/app/services/wrapped.py)). En los consejos, cada patrón conserva su descripción
   determinista si la IA falla. Cada uso del respaldo queda marcado en `ai_usage.uso_respaldo`.
4. **La extracción se valida, no se cree.** `_validar_gasto` en
   [`groq_client.py`](../../backend/app/services/groq_client.py) exige monto > 0 y ≤ 100.000.000, categoría dentro
   de la lista de la persona, fecha a menos de un año de hoy y descripción de máximo 200 caracteres; si algo falla,
   `ExpenseParseError` (422). Nunca inventa un monto.

## Alternativas consideradas

- **Que la IA calcule (o use herramientas para calcular).** Descartado: los números serían no reproducibles y
  difíciles de probar; con *function calling* se suma superficie de ataque ([ADR-009](009-capas-seguridad-ia.md)).
- **Mostrar la salida del modelo tal cual.** Descartado por los riesgos anteriores.
- **Sin IA, solo plantillas.** Es el respaldo; la IA aporta tono y variedad.

## Consecuencias

- El coach nunca deja de responder: si Groq falla o se agota el cupo, el chat contesta con el respaldo
  (`sin_cupo` o `chat`) y **no guarda el turno** (`id = SIN_GUARDAR`), para que el historial que se reenvía al
  modelo no lleve textos de respaldo.
- Las cifras son verificables con pruebas unitarias sin IA
  ([`tests/test_budget_calculator.py`](../../backend/tests/test_budget_calculator.py),
  [`tests/test_coach.py`](../../backend/tests/test_coach.py),
  [`tests/test_groq_caido.py`](../../backend/tests/test_groq_caido.py)).
- `inventa_cifras` es una heurística: puede descartar un buen mensaje que reformula una cifra (p. ej. "la mitad"
  no se detecta; "50 %" sí).
- **Excepción a "el parseo no guarda nada":** `POST /expenses/parse` y `POST /expenses/parse-receipt` solo
  devuelven el borrador, pero **`POST /expenses/from-text` parsea y guarda en un paso**
  ([`routers/expenses.py`](../../backend/app/routers/expenses.py)). La app móvil no lo usa (solo llama a `/parse`
  y `/parse-receipt`, [`mobile/lib/data/api.dart`](../../mobile/lib/data/api.dart)), pero el endpoint existe.
