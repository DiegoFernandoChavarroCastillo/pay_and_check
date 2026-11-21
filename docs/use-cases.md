# Casos de uso y contexto

Mermaid no tiene un tipo nativo de diagrama de casos de uso UML; se modela con `flowchart` (actores como
círculos, casos de uso como óvalos, frontera del sistema como `subgraph`).

## Diagrama de contexto general

Qué es el sistema, quién lo usa y con qué sistemas externos habla.

```mermaid
flowchart LR
    Persona(["Persona usuaria<br/>(Android, iPhone o PC)"])

    subgraph PC["Pay & Check"]
        direction TB
        App["App Flutter<br/>APK Android"]
        Web["App Flutter<br/>versión web"]
        API["API REST FastAPI"]
        DB[("PostgreSQL")]
        App -- "HTTPS + JSON, JWT" --> API
        Web -- "HTTPS + JSON, JWT" --> API
        API -- "SQL" --> DB
    end

    Groq["Groq<br/>LLM: parseo de texto y redacción del coach"]
    GoogleID["Google Identity<br/>inicio de sesión"]
    SMS["SMS del banco<br/>bandeja del teléfono"]
    OS["Servicios del dispositivo<br/>cámara, micrófono, notificaciones locales"]
    Plat["AWS EC2 + Caddy (API), Neon (base de datos),<br/>Vercel (web), GitHub Actions / Releases (CI, APK y web)"]

    Persona -- "registra movimientos,<br/>consulta disponible, chatea con el coach" --> App
    Persona -- "lo mismo desde el navegador<br/>(sin recibos, SMS ni recordatorios)" --> Web
    App -- "avisos locales,<br/>borradores para confirmar" --> Persona
    SMS -- "lectura con permiso" --> App
    OS <--> App
    API -- "chat.completions" --> Groq
    App -- "Google Sign-In" --> GoogleID
    Web -- "botón de Google" --> GoogleID
    API -- "verifica id_token" --> GoogleID
    Plat -. "aloja / compila" .-> PC
```

Límites del sistema: la versión web no lee SMS ni notificaciones, no reconoce recibos y no programa
recordatorios ([ADR-010](decisiones/010-version-web-respaldo.md)); no se conecta a bancos (los aportes a metas son dinero virtual), no tiene servidor de push
(las notificaciones son locales) y la IA nunca calcula cifras.

## Diagrama de casos de uso

Actores: **Persona usuaria** (principal), **Titular del plan Familiar** y **Bienestar Universitario**
(secundarios humanos), **Groq** y **Google Identity** (sistemas).

```mermaid
flowchart LR
    U(("Persona<br/>usuaria"))
    G(("Groq<br/>LLM"))
    GI(("Google<br/>Identity"))
    T(("Titular<br/>Familiar"))
    B(("Bienestar<br/>Universitario"))

    subgraph SYS["Pay & Check"]
        direction TB

        subgraph Cuenta["Cuenta"]
            UC1(["Registrarse / iniciar sesión"])
            UC2(["Iniciar sesión con Google"])
            UC3(["Editar perfil: tono del coach,<br/>idioma, zona horaria"])
            UC4(["Borrar cuenta y datos"])
        end

        subgraph Presupuesto["Presupuesto"]
            UC5(["Definir presupuesto del periodo"])
            UC6(["Ver disponible por día<br/>y riesgo de agotamiento"])
            UC7(["Gestionar categorías y límites"])
        end

        subgraph Movimientos["Movimientos"]
            UC8(["Registrar gasto manual"])
            UC9(["Registrar gasto por texto o voz"])
            UC10(["Registrar gasto por foto de recibo"])
            UC11(["Registrar gasto desde SMS del banco"])
            UC12(["Registrar ingreso"])
            UC13(["Confirmar o editar borrador"])
            UC14(["Consultar, editar y borrar movimientos"])
            UC15(["Gestionar gastos fijos<br/>pagar u omitir vencidos"])
        end

        subgraph Coach["Coach"]
            UC16(["Hacer check-in emocional"])
            UC17(["Recibir reacción tras un gasto"])
            UC18(["Ver consejos del día"])
            UC19(["Chatear con el coach"])
        end

        subgraph Progreso["Progreso"]
            UC20(["Crear metas y apartar dinero"])
            UC21(["Aceptar y seguir retos"])
            UC22(["Ver puntos, nivel, racha e insignias"])
        end

        subgraph Reportes["Reportes"]
            UC23(["Ver tendencia semanal"])
            UC24(["Ver reporte semanal"])
            UC25(["Ver resumen mensual"])
        end

        subgraph Decidir["Decidir antes de gastar"]
            UC26(["¿Me alcanza?<br/>de contado o a cuotas"])
            UC27(["Planear gastos que vienen<br/>y marcarlos como pagados"])
            UC28(["Dividir una vaca<br/>y cobrar lo que le deben"])
        end

        subgraph Planes["Planes y universidad"]
            UC29(["Ver y cambiar de plan<br/>canjear código de convenio o familiar"])
            UC30(["Compartir progreso con el titular"])
            UC31(["Ver progreso de la familia"])
            UC32(["Ver apoyos de la universidad<br/>y mostrar interés"])
            UC33(["Consultar el panel agregado<br/>(k ≥ 5)"])
        end
    end

    U --- UC1 & UC2 & UC3 & UC4
    U --- UC5 & UC6 & UC7
    U --- UC8 & UC9 & UC10 & UC11 & UC12 & UC14 & UC15
    U --- UC16 & UC18 & UC19
    U --- UC20 & UC21 & UC22
    U --- UC23 & UC24 & UC25
    U --- UC26 & UC27 & UC28
    U --- UC29 & UC30 & UC32
    T --- UC31
    B --- UC33

    UC9 -. "include" .-> UC13
    UC10 -. "include" .-> UC13
    UC11 -. "include" .-> UC13
    UC8 -. "extend" .-> UC17
    UC13 -. "extend" .-> UC17

    UC2 --- GI
    UC9 --- G
    UC10 --- G
    UC11 --- G
    UC17 --- G
    UC18 --- G
    UC19 --- G
    UC24 --- G
```

## Trazabilidad

| Casos de uso | Endpoints (ver [api.md](api.md)) |
|---|---|
| UC1–UC4 | `/auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`, `/auth/me` |
| UC5–UC7 | `/budgets`, `/budgets/active/summary`, `/categories` |
| UC8, UC14 | `/expenses`, `/expenses/{id}` |
| UC9, UC10, UC11, UC13 | `/expenses/parse`, `/expenses/parse-receipt`, luego `POST /expenses` (SMS con `source="sms"`) |
| UC12 | `/incomes` (la IA distingue ingresos con `tipo="ingreso"` en `/expenses/parse`) |
| UC15 | `/recurring-expenses`, `/pending`, `/{id}/pay`, `/{id}/skip` |
| UC16–UC19 | `/checkins`, `/coach/reaction`, `/coach/insights`, `/coach/chat` |
| UC20–UC22 | `/goals`, `/challenges`, `/gamification/profile` |
| UC23–UC25 | `/reports/trends`, `/reports/weekly`, `/reports/monthly-wrapped`, `/reports/repeated` |
| UC26 | `/budgets/active/simulate`, `/budgets/simulate-credit` |
| UC27 | `/planned-expenses`, `/planned-expenses/{id}/done` (solo marca; no crea gasto) |
| UC28 | `/expenses/split`, `/receivables`, `/receivables/{id}/paid` |
| UC29–UC31 | `/plans`, `/me/subscription`, `/me/subscription/redeem`, `/me/subscription/share-progress`, `/me/family/progress` |
| UC32 | `/support`, `/support/{id}/interest` |
| UC33 | `/panel/{org_id}` (HTML con token de la universidad) |

En la versión web no están UC10, UC11 ni los recordatorios de UC15 (el resto de UC15 sí: la lista de gastos
fijos por pagar).

Cuando Groq falla o no hay `GROQ_API_KEY`: el parseo (UC9–UC11) responde 503 y se usa el formulario manual; el
coach y el reporte semanal usan textos de respaldo deterministas.
