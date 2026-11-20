# Reglas de cálculo del presupuesto

Este documento explica cómo se calcula cada cifra del resumen de presupuesto (`GET /budgets/active/summary`).
Se escribió leyendo el código, y el código manda: si cambia una regla, hay que actualizar este documento
y las pruebas de `backend/tests/test_budget_calculator.py`.

- **Cálculo:** `backend/app/services/budget_calculator.py`, función `calculate_budget_summary` (con su
  ayudante `_proyectar_agotamiento`).
- **Totales de entrada:** `backend/app/services/budget_totals.py`, función `summary_for`.
- **"Hoy":** viene de `today_for(user)` (`backend/app/core/time.py`), es decir, la fecha en la zona horaria
  de la persona y no la del servidor. El cálculo recibe `today` como argumento y nunca usa `date.today()`.

## 1. Entradas

`summary_for(session, budget, today)` suma de la base de datos (`_suma`, con `COALESCE(SUM(...), 0)`):

| Entrada | Origen | Filtro |
|---|---|---|
| `monto_total` | `Budget.monto_total` | el propio presupuesto |
| `gastado_total` | `SUM(Expense.monto)` | `Expense.budget_id == budget.id` |
| `ingresos_total` | `SUM(Income.monto)` | `Income.budget_id == budget.id` |
| `apartado_total` | `SUM(GoalContribution.monto)` | `GoalContribution.budget_id == budget.id` |

Los filtros van por `budget_id` y no por fecha: cuenta todo lo que esté ligado al presupuesto, sea cual sea su fecha.

## 2. Fórmulas

Todas están en `calculate_budget_summary` (`budget_calculator.py`), salvo que se indique otra función.

### 2.1 Disponible total

```
disponible_total = monto_total + ingresos_total − gastado_total − apartado_total
```

- Los ingresos aumentan lo disponible, pero `monto_total` no cambia.
- Lo apartado para metas de ahorro deja de estar disponible para gastar.
- No depende de la fecha y puede ser negativo (si se gastó de más).
- Se redondea a centavos con `ROUND_HALF_UP` (`_redondear`).

### 2.2 Días restantes

```
si today > fecha_fin:   dias_restantes = 0
si no:                  dias_restantes = (fecha_fin − max(today, fecha_inicio)).days + 1
```

Se cuentan ambos extremos: si hoy es el último día, queda 1. Si el presupuesto aún no empieza, se cuenta el periodo completo.

### 2.3 Semanas restantes

```
semanas_restantes = dias_restantes / 7
```

La respuesta lo muestra redondeado a 2 decimales (`ROUND_HALF_UP`), pero el cálculo por semana usa el valor
**sin redondear**.

### 2.4 Disponible por día

```
disponible_por_dia = redondear(disponible_total / dias_restantes)   si dias_restantes > 0
                   = 0.00                                           si no
```

### 2.5 Disponible por semana

```
disponible_por_semana = redondear(disponible_total / semanas_restantes)   si semanas_restantes > 0
                      = 0.00                                              si no
```

Equivale a `disponible_total × 7 / dias_restantes`. Cuando quedan menos de 7 días, la cifra es **mayor** que
el disponible total, porque es una tasa semanal y no lo que queda en la semana.

### 2.6 En riesgo y fecha proyectada de agotamiento

Están en `_proyectar_agotamiento(budget, gastado_total, disponible_total, today)`:

```
referencia          = min(today, fecha_fin)
si referencia < fecha_inicio  →  en_riesgo = False, fecha = None      (aún no empieza)

dias_transcurridos  = max((referencia − fecha_inicio).days + 1, 1)
periodo             = (fecha_fin − fecha_inicio).days + 1
ventana             = max(dias_transcurridos, min(7, periodo))          (VENTANA_MINIMA_RITMO)
ritmo_diario_real   = (gastado_total − gasto_fijo_total) / ventana
si ritmo_diario_real <= 0     →  en_riesgo = False, fecha = None      (sin gasto)

dias_que_alcanza    = truncar_hacia_cero(disponible_total / ritmo_diario_real)   (ROUND_DOWN)
fecha_proyectada    = today + dias_que_alcanza
en_riesgo           = fecha_proyectada < fecha_fin
```

- **Ventana mínima de una semana** (noviembre 2026): con uno o dos días de datos, una sola compra grande se
  extrapolaba a todo el periodo y disparaba una alarma falsa. El ritmo se mide sobre al menos 7 días, o sobre el
  periodo entero si es más corto. Si el gasto ya pasó del total, igual sale en riesgo porque el disponible es
  negativo.
- **Los gastos fijos programados no son ritmo:** `gasto_fijo_total` es la suma de los gastos con
  `recurring_expense_id` (arriendo, plan del celular). Se descuentan del disponible, pero no se extrapolan: pagar
  el arriendo el día 1 no significa gastar eso cada día. Pruebas en `tests/test_budget_calculator.py`.
- El ritmo se calcula solo con lo **gastado**. Los ingresos y lo apartado no lo cambian, pero sí cambian
  el `disponible_total` que se divide.
- Se usa `<` estricto: si la fecha proyectada cae justo en `fecha_fin`, el presupuesto **no** está en riesgo.

## 3. Casos especiales

| Caso | Condición | Qué pasa |
|---|---|---|
| **Vencido** | `today > fecha_fin` | `dias_restantes = 0`, `semanas_restantes = 0.00`, por día y por semana `0.00` (para no dividir entre cero). `disponible_total` sigue mostrando el saldo real. La proyección usa `referencia = fecha_fin`, o sea, el ritmo del periodo completo (ver decisión pendiente D1). |
| **No iniciado** | `today < fecha_inicio` | `dias_restantes` = periodo completo, y el por día y el por semana se reparten sobre todo el periodo. `en_riesgo = False` y `fecha = None` siempre, aunque ya haya gastos ligados. |
| **Sin gasto** | `gastado_total = 0` | `en_riesgo = False` y `fecha = None`. |
| **Ingresos** | `ingresos_total > 0` | Se suman a `disponible_total` sin tocar `monto_total`, y no cambian el ritmo de gasto. |
| **Dinero apartado en metas** | `apartado_total > 0` | Se resta de `disponible_total`. Además, `routers/goals.py` (aportar a una meta) rechaza un aporte mayor que `summary_for(...).disponible_total`, así que no se puede apartar dinero que no hay. |
| **Gasto mayor que el disponible** | `disponible_total < 0` | Por día y por semana salen negativos, y la fecha proyectada cae **antes de hoy** (ver D2). |

## 4. Casos calculados a mano

Cada caso es una prueba en `backend/tests/test_budget_calculator.py`, con la fecha fija.

### Caso 1. Normal: alcanza hasta el fin del periodo

Presupuesto de 1.200.000 del 2026-11-01 al 2026-11-30 (30 días). Hoy es **2026-11-11**. Gastado 300.000,
ingresos 100.000, apartado en metas 50.000.

| Cifra | Cálculo | Resultado |
|---|---|---|
| disponible_total | 1.200.000 + 100.000 − 300.000 − 50.000 | **950.000,00** |
| dias_restantes | (30 nov − 11 nov) + 1 = 19 + 1 | **20** |
| semanas_restantes | 20 / 7 = 2,857… | **2,86** |
| disponible_por_dia | 950.000 / 20 | **47.500,00** |
| disponible_por_semana | 950.000 × 7 / 20 | **332.500,00** |
| dias_transcurridos | (11 nov − 1 nov) + 1 | 11 |
| ritmo_diario_real | 300.000 / 11 | 27.272,7272… |
| dias_que_alcanza | 950.000 × 11 / 300.000 = 34,83 → truncado | 34 |
| fecha_proyectada_agotamiento | 11 nov + 34 días | **2026-12-15** |
| en_riesgo | 15 dic < 30 nov → no | **False** |

### Caso 2. Se agota antes del fin del periodo

Presupuesto de 600.000 del 2026-11-01 al 2026-11-30. Hoy es **2026-11-10**. Gastado 400.000, sin ingresos
ni dinero apartado.

| Cifra | Cálculo | Resultado |
|---|---|---|
| disponible_total | 600.000 − 400.000 | **200.000,00** |
| dias_restantes | (30 nov − 10 nov) + 1 | **21** |
| semanas_restantes | 21 / 7 | **3,00** |
| disponible_por_dia | 200.000 / 21 = 9.523,8095… | **9.523,81** |
| disponible_por_semana | 200.000 / 3 = 66.666,666… | **66.666,67** |
| dias_transcurridos | (10 nov − 1 nov) + 1 | 10 |
| ritmo_diario_real | 400.000 / 10 | 40.000 |
| dias_que_alcanza | 200.000 / 40.000 | 5 |
| fecha_proyectada_agotamiento | 10 nov + 5 días | **2026-11-15** |
| en_riesgo | 15 nov < 30 nov → sí | **True** |

### Caso 3. Vencido

Presupuesto de 500.000 del 2026-10-01 al 2026-10-31 (31 días). Hoy es **2026-11-05**. Gastado 520.000,
ingresos 30.000, sin dinero apartado.

| Cifra | Cálculo | Resultado |
|---|---|---|
| disponible_total | 500.000 + 30.000 − 520.000 | **10.000,00** |
| dias_restantes | 5 nov > 31 oct → vencido | **0** |
| semanas_restantes | 0 / 7 | **0,00** |
| disponible_por_dia | sin días restantes | **0,00** |
| disponible_por_semana | sin semanas restantes | **0,00** |
| referencia | min(5 nov, 31 oct) | 31 oct |
| dias_transcurridos | (31 oct − 1 oct) + 1 | 31 |
| ritmo_diario_real | 520.000 / 31 | 16.774,19… |
| dias_que_alcanza | 10.000 × 31 / 520.000 = 0,596 → truncado | 0 |
| fecha_proyectada_agotamiento | 5 nov + 0 días | **2026-11-05** |
| en_riesgo | 5 nov < 31 oct → no | **False** |

## 5. Decisiones pendientes

Estas reglas parecen dudosas. **No se cambió el código**: se anotan aquí para que el equipo decida, y las
pruebas fijan el comportamiento actual.

- **D1. Fecha proyectada en un presupuesto vencido.** Si el presupuesto está vencido, igual se devuelve una
  fecha proyectada (en el caso 3, hoy mismo, 2026-11-05, que es posterior al fin). Esa fecha no tiene sentido
  para un periodo que ya cerró. *Propuesta:* si `today > fecha_fin`, devolver `fecha = None` y `en_riesgo = False`.
- **D2. Fecha proyectada en el pasado cuando ya se gastó de más.** Si `disponible_total < 0`,
  `dias_que_alcanza` sale negativo y la fecha cae antes de hoy. Por ejemplo, con 100.000 del 1 al 30 de nov,
  150.000 gastados y hoy 10 de nov, la fecha es el 2026-11-07. El aviso de `patterns.py` diría "tu presupuesto
  alcanzaría hasta el 7 de nov" cuando eso ya pasó. *Propuesta:* si `disponible_total <= 0`, usar
  `fecha = today` (o un estado "agotado") y mantener `en_riesgo = True`.
- **D3. Disponible por día y por semana negativos.** Con `disponible_total < 0`, la app recibe cifras
  negativas (−2.380,95 por día en el ejemplo de D2). Hay que decidir si se muestran así o con un tope en 0 y un
  mensaje de "excedido".
- **D4. Por semana mayor que el total en la última semana.** Con menos de 7 días restantes,
  `disponible_por_semana` es mayor que `disponible_total` (por ejemplo, 3 días y 30.000 disponibles dan 70.000
  "por semana"). La fórmula es correcta como tasa, pero puede confundir. *Propuesta:* mostrar
  `min(disponible_por_semana, disponible_total)` o bien ocultarlo cuando quedan menos de 7 días.
- **D5. No iniciado con gastos ya ligados.** Si hay gastos ligados a un presupuesto que aún no empieza, no se
  calcula ningún riesgo. Es un caso raro, pero hay que confirmar que es lo que se quiere.
- **D6. Redondeo a centavos.** Todo se redondea a 0,01 con `ROUND_HALF_UP`, aunque la moneda principal (COP)
  no usa centavos en la práctica. Hay que decidir si la app debe mostrar enteros.
