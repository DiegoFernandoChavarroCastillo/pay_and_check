# Modelo de datos

Tablas definidas en `backend/app/models/*` (SQLModel) y versionadas con Alembic (`backend/alembic/versions/`,
9 migraciones desde `6a4686a52aeb_init`). Montos en `Numeric(12, 2)`.

## Diagrama 3 — Entidad-relación

```mermaid
erDiagram
    groups ||--o{ users : "group_id (reservado)"
    users ||--o{ budgets : "owner_id"
    users ||--o{ categories : "owner_id (nulo = por defecto)"
    users ||--o{ category_limits : "user_id"
    categories ||--o{ category_limits : "category_id"
    users ||--o{ expenses : "user_id"
    budgets ||--o{ expenses : "budget_id"
    categories ||--o{ expenses : "category_id"
    recurring_expenses |o--o{ expenses : "recurring_expense_id"
    users ||--o{ incomes : "user_id"
    budgets ||--o{ incomes : "budget_id"
    users ||--o{ recurring_expenses : "user_id"
    categories ||--o{ recurring_expenses : "category_id"
    users ||--o{ emotional_checkins : "user_id"
    users ||--o{ coach_messages : "user_id"
    users ||--o{ goals : "user_id"
    goals ||--o{ goal_contributions : "goal_id"
    budgets ||--o{ goal_contributions : "budget_id"
    users ||--o{ goal_contributions : "user_id"
    users ||--o{ challenges : "user_id"
    categories |o--o{ challenges : "category_id"
    users ||--o{ achievements : "user_id"
    users ||--o{ point_events : "user_id"

    users {
        int id PK
        string email UK
        string hashed_password "nullable"
        string google_id UK "nullable"
        string nombre
        string coach_tone
        string idioma
        string zona_horaria
        int group_id FK
    }
    budgets {
        int id PK
        int owner_id FK
        numeric monto_total
        date fecha_inicio
        date fecha_fin
    }
    categories {
        int id PK
        string nombre
        int owner_id FK "nullable"
        string tipo "fijo | opcional"
        numeric limite "nullable"
    }
    category_limits {
        int id PK
        int user_id FK
        int category_id FK
        numeric limite
    }
    expenses {
        int id PK
        int user_id FK
        int budget_id FK
        int category_id FK
        numeric monto
        string descripcion
        string texto_original
        int recurring_expense_id FK
        string source "manual|texto|voz|ocr|sms|recurrente"
        string comercio
        date fecha
    }
    incomes {
        int id PK
        int user_id FK
        int budget_id FK
        numeric monto
        string descripcion
        date fecha
    }
    recurring_expenses {
        int id PK
        int user_id FK
        int category_id FK
        numeric monto
        string frecuencia "semanal | mensual"
        int dia_semana
        int dia_mes
        date fecha_inicio
        bool activo
        date omitido_hasta
    }
    emotional_checkins {
        int id PK
        int user_id FK
        date fecha
        string animo
        string nota
    }
    coach_messages {
        int id PK
        int user_id FK
        string tipo "insights | chat_user | chat_coach"
        string contenido
        date fecha
    }
    goals {
        int id PK
        int user_id FK
        string nombre
        numeric monto_objetivo
        date fecha_limite
        string estado "activa | cumplida"
        date cumplida_en
    }
    goal_contributions {
        int id PK
        int goal_id FK
        int user_id FK
        int budget_id FK
        numeric monto
        date fecha
    }
    challenges {
        int id PK
        int user_id FK
        string tipo
        int category_id FK
        numeric objetivo
        numeric linea_base
        date fecha_inicio
        date fecha_fin
        string estado "activo|cumplido|fallido"
        int puntos
    }
    achievements {
        int id PK
        int user_id FK
        string codigo
        datetime unlocked_at
    }
    point_events {
        int id PK
        int user_id FK
        string clave
        string tipo
        int puntos
        date fecha
    }
    groups {
        int id PK
        string nombre
    }
```

## Reglas de integridad

| Tabla | Restricción |
|---|---|
| `users` | `email` y `google_id` únicos; `CHECK (hashed_password IS NOT NULL OR google_id IS NOT NULL)` |
| `categories` | `owner_id` nulo = categoría por defecto compartida (sembrada por `app/db/seed.py`: comida, transporte, entretenimiento, salud, servicios, otros); `CHECK tipo IN ('fijo','opcional')` |
| `category_limits` | `UNIQUE (user_id, category_id)`: el límite personal sobre una categoría compartida (`Category.limite` solo aplica a las propias) |
| `expenses` | `CHECK source IN (...)`; `UNIQUE (recurring_expense_id, fecha)` evita duplicar un gasto fijo |
| `emotional_checkins` | `UNIQUE (user_id, fecha)` (uno por día, reemplaza); `CHECK animo IN ('ansioso','preocupado','neutral','tranquilo','confiado')` |
| `challenges` | `CHECK tipo IN ('reducir_categoria','dias_sin_gasto','checkins','registro_diario','aportar_meta','semana_en_ritmo')`; `CHECK estado` |
| `achievements` | `UNIQUE (user_id, codigo)`; el catálogo de insignias vive en `services/gamification.py` |
| `point_events` | `UNIQUE (user_id, clave)`: libro de puntos idempotente |
| `goals` | `CHECK estado IN ('activa','cumplida')`; progreso = suma de `goal_contributions`, nunca auto-reportado |

## Notas

- `groups` y `users.group_id` están preparados para un modo familiar/grupal **no usado** en el MVP.
- Un `Expense`, `Income` o `GoalContribution` pertenece al `Budget` cuyo rango contiene su `fecha`
  (`services/budget_lookup.find_budget_for_date`); fuera de todo presupuesto la API responde 400.
- `GoalContribution` es dinero virtual: se descuenta del disponible del presupuesto (`apartado_total`).
- `DELETE /auth/me` borra la cuenta y todos sus datos en orden compatible con las llaves foráneas.
- Aplicar el esquema: `alembic upgrade head` (en producción lo hace `backend/start.sh`). Los tests usan
  `SQLModel.metadata.create_all` sobre SQLite.
