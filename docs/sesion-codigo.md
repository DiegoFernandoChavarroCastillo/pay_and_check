# Sesión de código (PS-44)

Guía de la sesión en la que el equipo recorre el código y cada integrante corre la app. Sirve también para
quien llegue después: en una hora se entiende dónde está cada cosa.

## 1. Correr todo (15 min)

Cada integrante sigue [setup.md](setup.md) en su equipo y deja capturas de:

1. `uv run pytest` en verde (backend).
2. `flutter test` en verde (móvil).
3. La app abierta contra su backend local (emulador o teléfono con `adb reverse tcp:8000 tcp:8000`).
4. Datos de demo cargados: `cd backend && uv run python -m app.db.seed_demo`. Entra con
   `valentina@demo.payandcheck.app` / `Demo2026!`.

Si algo de `setup.md` falla, se corrige en el mismo PR que cierra el ticket.

## 2. Estructura del repo

```
backend/app/
  main.py          crea la app FastAPI, registra los routers y los manejadores de error (422 y 500)
  deps.py          get_current_user: lee el Bearer y devuelve el User (401 si no)
  core/            config (variables de entorno), security (JWT y hash), time (today_for), rate_limit
  routers/         una ruta HTTP = una función; valida, consulta y llama a services
  services/        lógica: cálculo del presupuesto, coach, IA, planes, gamificación, panel
  models/          tablas SQLModel (una por archivo)
  schemas/         modelos Pydantic de entrada y salida de la API
  db/              sesión, semilla de categorías, seed_demo, scripts de convenios y reporte de IA
  templates/       HTML del panel de Bienestar
backend/alembic/   migraciones (una sola cabeza)
backend/tests/     pytest hermético (SQLite en memoria, IA falsa)

mobile/lib/
  main.dart, app.dart   arranque, tema, rutas e idioma
  core/api/             api_client.dart: Dio con Authorization y renovación del token
  data/                 api.dart (un método por endpoint), models.dart, providers.dart (Riverpod), session.dart
  features/<pantalla>/  una carpeta por función: home, transactions, budget, coach, planning, progress, ...
  l10n/                 app_es.arb y app_en.arb (todo texto visible va aquí)
```

## 3. Flujo de una petición: registrar un gasto (15 min)

Se sigue con el depurador o con `print` el caso «almuerzo 18 mil» escrito en la app:

1. **App**: `features/transactions/add_sheet.dart` → `Api.parseExpense` (`data/api.dart`) →
   `POST /expenses/parse`. `core/api/api_client.dart` pone el token.
2. **Router**: `routers/expenses.py::parse_expense`. Antes de entrar corren las dependencias:
   `get_current_user` (`deps.py`) y `limite_ia` (máximo 20 solicitudes de IA por minuto, `core/rate_limit.py`).
3. **Cupo**: `services/ia_uso.py::usar` abre el registro de uso; si el plan ya gastó su cupo del mes, responde 402
   y la app abre el formulario manual.
4. **IA**: `services/groq_client.py::parse_expense_text` arma el prompt (`services/prompts.py`), sanea el texto
   (`services/ia_seguridad.py`), llama a Groq en `_chat` (con respaldo en `_chat_respaldo`) y valida el JSON en
   `_validar_gasto`. Si la IA devuelve una categoría que no existe o una fecha imposible, se corrige ahí.
5. **Respuesta**: un borrador (`schemas/expense.py::ExpenseParseResponse`). **No se guarda nada**: la persona
   confirma en `expense_form_screen.dart`, que llama a `POST /expenses` (`create_expense`), y ese sí escribe en
   `models/expense.py`.
6. **Después**: la app pide `GET /budgets/active/summary` y el número del día se recalcula.

## 4. Las dos reglas que no se rompen (15 min)

**La IA redacta, no calcula.** Toda cifra sale de código determinista:

- `services/budget_calculator.py::calculate_budget_summary`: disponible total, por día y por semana, riesgo y fecha
  proyectada. Las fórmulas están en [reglas-calculo.md](reglas-calculo.md) y las prueba `tests/test_budget_calculator.py`.
- `services/simulador.py` («¿Me alcanza?» y planes de meta) y `services/credito.py` (cuotas).
- `services/coach.py`: arma el contexto con las «cifras ya calculadas», pide el texto a Groq y descarta la respuesta
  si trae una cifra que no estaba en el contexto (usa entonces el texto de respaldo).

**Defensa en capas contra prompt injection** ([seguridad.md](seguridad.md), [ia.md](ia.md)): se filtra la entrada
(`pedido_ajeno`, `marca_inyeccion`), el dato de la persona va delimitado (`como_datos`), se filtra la salida
(`filtra_salida`) y el modelo no tiene herramientas ni acceso a la base.

## 5. Ejercicio (15 min)

Cada integrante hace un cambio mínimo en su rama (por ejemplo, un texto nuevo en los dos `.arb` o un caso más en
un test), corre las pruebas y abre un PR con la plantilla (`.github/PULL_REQUEST_TEMPLATE.md`). Así se valida que todos
pueden compilar, probar y pasar por la protección de ramas.

## Registro de la sesión

| Integrante | Backend en verde | App corriendo | PR de prueba |
|---|---|---|---|
| Diego Chavarro | | | |
| Sebastián | | | |
| Julian | | | |
| David | | | |
| Stiven | | | |

Grabación: _(enlace)_
