# 📱 Especificación Técnica: App de Finanzas Personales con Coach Psicológico, Gamificación y Automatización

> **Documento para agente de código**  
> Este documento define la visión, arquitectura, funcionalidades y flujos de una aplicación de finanzas personales diferenciada. El objetivo es construir una app que **no solo registre gastos**, sino que actúe como un **coach financiero emocional**, gamifique el comportamiento y **ejecute acciones automáticamente** con mínima intervención del usuario.

---

## ✅ Estado de implementación (13 de octubre de 2026)

Este documento es la visión original y se conserva tal cual. Esta tabla dice qué parte existe hoy en la app;
el detalle está en `plan-app-movil.md` y `notas-iteracion-app-movil.md`.

| ID | Funcionalidad | Estado |
|----|---------------|--------|
| C-01 | Mensaje al registrar una transacción | Hecho |
| C-02 | Check-in emocional diario | Hecho |
| C-03 | Alertas proactivas de riesgo | Parcial: aviso cuando el presupuesto no alcanzaría al ritmo actual |
| C-04 | Consejos accionables contextuales | Hecho, con acción de un toque |
| C-05 | Ejecución asistida con consentimiento | Parcial: apartar a una meta, aceptar un reto o poner un límite con un toque; sin mover dinero real |
| C-06 | Predicción de déficit con calendario | No |
| C-07 | Tono configurable | Hecho (motivador, directo, con humor, minimalista) |
| G-01 | Retos personalizados | Hecho: 6 tipos, sugeridos según los datos |
| G-02 | Metas con verificación real | Hecho, con dinero apartado dentro del presupuesto |
| G-03 | Puntos y niveles | Hecho |
| G-04 | Insignias y logros | Hecho: 23 |
| G-05 | Ligas y competición social | No |
| G-06 | Retos colaborativos | No |
| G-07 | Recompensas desbloqueables | No |
| G-08 | Wrapped mensual | Hecho (sin fotos) |
| A-01 | OCR de recibos | Hecho, reconociendo el texto en el teléfono; sin probar con recibos reales |
| A-02 | Lectura de correos (Gmail) | No |
| A-03 | Lectura de SMS | Hecho bajo demanda (al abrir la app), con aprobación de cada movimiento |
| A-04 | Categorización automática con IA | Hecho al registrar por texto, voz, recibo o SMS |
| A-05 | Ejecución de acciones con el banco | No |
| A-06 | Sincronización con calendario | No |
| A-07 | Detección de suscripciones | No. En su lugar, gastos fijos que programa la persona, con recordatorio |

Diferencias de fondo frente a esta visión: el stack es FastAPI + Groq + Flutter (no el sugerido en la
sección 4), no hay conexión bancaria ni servidor de push, y la IA nunca calcula: solo redacta sobre cifras
que salen de código determinista.

---

## 🎯 1. Visión del Producto

**Nombre provisional:** `FinCoach` (ajustable)

**Problema a resolver:**
Las apps de finanzas actuales son contadores pasivos. Muestran números, pero no cambian el comportamiento del usuario. La gente evita mirar sus finanzas por ansiedad, culpa o simple pereza. Además, la categorización manual es tediosa y abandona a los pocos días.

**Solución:**
Una app que **captura datos automáticamente** (OCR + correos), **analiza el comportamiento con IA**, **actúa como coach psicológico** (motiva, aconseja, ejecuta), y **gamifica el progreso** con retos verificables por datos reales.

**Propuesta de valor única:**
> "La única app de finanzas que no solo te dice qué hacer con tu dinero, sino que lo hace contigo, te motiva sin juzgarte y convierte tus hábitos financieros en un juego con recompensas reales."

---

## 🧩 2. Los Tres Pilares del Producto

### 🧠 Pilar 1: Coach Psicológico (no un contador)

**Objetivo:** Que cada interacción con la app genere una respuesta emocional positiva y accionable, no culpa.

**Funcionalidades:**

| ID | Funcionalidad | Descripción |
|----|---------------|-------------|
| C-01 | **Registro emocional de transacciones** | Cada vez que se registra un gasto/ingreso, la app muestra un mensaje motivacional contextual (no genérico). Ej: "Buen movimiento, esto te acerca a tu meta del viaje ✈️" |
| C-02 | **Check-in diario de 1 minuto** | El usuario registra cómo se siente con su dinero (ansiedad, confianza, control). La IA correlaciona emociones con patrones de gasto. |
| C-03 | **Alertas proactivas de riesgo** | Si detecta patrón de gasto impulsivo (ej. viernes noche), sugiere preventivamente mover dinero a "alcancía bloqueada". |
| C-04 | **Consejos accionables contextuales** | En lugar de "reduce gastos", dice: "Gastas 30% más en delivery los fines de semana. Si reduces 20%, en 3 meses pagas esa deuda." |
| C-05 | **Ejecución asistida con consentimiento** | La IA propone una acción concreta: "¿Muevo $20 a tu fondo de emergencia?" y el usuario aprueba con un tap. |
| C-06 | **Predicción de déficit** | Cruza calendario (cumpleaños, matrículas) con flujo de caja y alerta antes de que ocurra. |
| C-07 | **Tono configurable** | El usuario elige el estilo del coach: motivador, directo, humorístico, minimalista. |

**Lógica clave:**
- La IA **nunca** usa lenguaje culposo. Siempre reformula en positivo.
- Cada consejo viene con **acción de un solo tap**.
- El coach **aprende** del historial: si el usuario ignora sugerencias de inversión, deja de mostrarlas.

---

### 🎮 Pilar 2: Gamificación con Propósito

**Objetivo:** Convertir hábitos financieros saludables en un sistema de progreso verificable.

**Funcionalidades:**

| ID | Funcionalidad | Descripción |
|----|---------------|-------------|
| G-01 | **Retos personalizados** | La IA propone retos basados en patrones detectados. Ej: "Reduce 20% tu gasto de ocio este mes." |
| G-02 | **Metas de ahorro con verificación real** | El usuario define meta ($X en Y meses). La app **verifica con datos reales** (no auto-reporte) si se cumple. |
| G-03 | **Sistema de puntos y niveles** | Puntos por: registrar transacciones, cumplir retos, mantener racha, mejorar ratios. |
| G-04 | **Insignias y logros** | Ej: "Maestro del Viernes" (redujiste gasto nocturno), "Racha de 30 días", "Primer $1,000 ahorrados". |
| G-05 | **Ligas y competición social** | Compite con amigos por consistencia y mejora real (no por quién gasta menos). |
| G-06 | **Retos colaborativos** | "Juntos ahorramos $10,000 este mes" con progreso grupal. |
| G-07 | **Recompensas desbloqueables** | Cursos de inversión, herramientas premium, plantillas, acceso a funciones avanzadas. |
| G-08 | **Wrapped financiero mensual** | Resumen estilo Spotify Wrapped con fotos/recuerdos asociados a gastos. |

**Reglas de verificación:**
- Los logros se validan con **datos extraídos automáticamente** (OCR, Gmail, SMS).
- No hay auto-reporte de "ahorré X". La app lo calcula.
- Los puntos se otorgan por **consistencia y mejora de ratios**, no por montos absolutos (para no castigar a quienes ganan menos).

**Métricas de gamificación:**
- `ratio_ahorro = (ingresos - gastos) / ingresos`
- `consistencia = días con registro / días totales`
- `mejora_mensual = ratio_actual - ratio_mes_anterior`

---

### 🤖 Pilar 3: Automatización y Ejecución

**Objetivo:** Eliminar la fricción del registro manual y permitir que la app **actúe** por el usuario.

**Funcionalidades:**

| ID | Funcionalidad | Descripción | Viabilidad |
|----|---------------|-------------|------------|
| A-01 | **OCR de recibos** | El usuario toma foto de un recibo. La IA extrae: comerciante, fecha, total, categoría. | ✅ Alta (97-99% precisión) |
| A-02 | **Lectura de correos (Gmail API)** | Accede a correos de transacciones bancarias y crea gastos automáticamente. | ⚠️ Requiere evaluación CASA ($15K-$75K) |
| A-03 | **Lectura de SMS/notificaciones** | Alternativa menos restrictiva a Gmail para capturar transacciones. | ✅ Alta |
| A-04 | **Categorización automática con IA** | Infiere contexto: "Amazon + cumpleaños en calendario = regalo". | ✅ Alta |
| A-05 | **Ejecución de acciones** | Mover dinero a metas, programar reducciones de presupuesto, cancelar suscripciones. | ⚠️ Requiere integración bancaria |
| A-06 | **Sincronización con calendario** | Anticipa gastos futuros y ajusta presupuesto. | ✅ Alta |
| A-07 | **Detección de suscripciones** | Identifica cargos recurrentes y sugiere cancelar los no usados. | ✅ Alta |

**⚠️ Nota legal sobre Gmail API:**
- Requiere permiso `gmail.readonly` + OAuth 2.0.
- Google exige **evaluación de seguridad CASA** para producción.
- **Prohibido** usar datos para publicidad o venderlos.
- **Recomendación:** Lanzar MVP con OCR + SMS, y añadir Gmail como función premium post-validación.

---

## 🔄 3. Cómo se Conecta Todo: El Círculo Virtuoso

```
┌─────────────────────────────────────────────────────────────────┐
│                    CÍRCULO VIRTUOSO FINCOACH                     │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │  1. CAPTURA      │  OCR recibos + SMS + Gmail API + Manual
  │  AUTOMÁTICA      │  → Datos entran sin fricción
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  2. ANÁLISIS      │  IA detecta patrones, emociones,
  │  CONDUCTUAL       │  riesgos, oportunidades
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  3. COACH         │  Mensaje motivacional + consejo
  │  PSICOLÓGICO      │  accionable + propuesta de acción
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  4. GAMIFICACIÓN  │  Reto personalizado + puntos +
  │                   │  insignia + liga social
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  5. VERIFICACIÓN  │  Datos reales confirman logro
  │  AUTOMÁTICA       │  (no auto-reporte)
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  6. RECOMPENSA    │  Puntos + insignia + coach
  │  Y REFUERZO       │  sugiere siguiente acción
  └────────┬─────────┘
           │
           └──────────► Vuelve a 1 (nuevos datos)
```

**Ejemplo de flujo completo:**

1. **Captura:** Usuario paga en restaurante. Llega SMS del banco. La app lo registra automáticamente.
2. **Análisis:** IA detecta que es el 4to restaurante esta semana → patrón de gasto impulsivo.
3. **Coach:** "Has salido a comer 4 veces esta semana. ¿Todo bien? Si quieres, puedo mover $20 a tu meta del viaje para compensar."
4. **Gamificación:** "Reto: la próxima semana, reduce 1 salida a restaurante. Recompensa: 50 pts + insignia 'Equilibrio'".
5. **Verificación:** Al final de la semana, la app confirma con datos reales que se cumplió.
6. **Recompensa:** "+50 pts. Nivel: 'Estratega Financiero'. ¿Invierto el ahorro en tu fondo?"

---

## 🏗️ 4. Arquitectura Técnica Propuesta

### Stack sugerido

| Capa | Tecnología | Justificación |
|------|------------|---------------|
| **Frontend móvil** | React Native + Expo | Multiplataforma, rápido de iterar |
| **Backend** | Node.js + NestJS | Escalable, tipado, buena integración con IA |
| **Base de datos** | PostgreSQL + Redis | Relacional para transacciones, Redis para caché/sesiones |
| **IA/ML** | OpenAI API (GPT-4o) + Python (scikit-learn) | NLP para coach, ML para patrones |
| **OCR** | Google Vision API o Tesseract | Extracción de recibos |
| **Autenticación** | OAuth 2.0 (Google, Apple) | Estándar seguro |
| **Integración bancaria** | Plaid o Belvo | Conexión a cuentas |
| **Notificaciones** | Firebase Cloud Messaging | Push notifications |
| **Almacenamiento** | AWS S3 | Imágenes de recibos |
| **Analytics** | PostHog o Mixpanel | Tracking de comportamiento |

### Diagrama de arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE (React Native)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Dashboard│  │  Coach   │  │  Retos   │  │ Perfil   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (NestJS)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Auth     │  │ Transac. │  │ Coach    │  │ Gamif.   │        │
│  │ Module   │  │ Module   │  │ Module   │  │ Module   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │  OpenAI API  │    │  OCR Service │
│  (datos)     │    │  (coach/IA)  │    │  (Vision)    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Redis       │    │  ML Models   │    │  S3 Storage  │
│  (caché)     │    │  (patrones)  │    │  (recibos)   │
└──────────────┘    └──────────────┘    └──────────────┘
        │
        ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Plaid/Belvo │    │  Gmail API   │    │  SMS Parser  │
│  (bancos)    │    │  (correos)   │    │  (Android)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Modelo de datos (entidades principales)

```sql
-- Usuarios
users (id, email, name, coach_tone, created_at)

-- Transacciones
transactions (id, user_id, amount, category, merchant, date, source, receipt_url)

-- Metas
goals (id, user_id, name, target_amount, current_amount, deadline, status)

-- Retos
challenges (id, user_id, description, metric, target_value, current_value, status, points)

-- Logros
achievements (id, user_id, type, name, unlocked_at, points)

-- Check-ins emocionales
emotional_checkins (id, user_id, mood, note, date)

-- Acciones ejecutadas
actions (id, user_id, type, payload, status, executed_at)

-- Patrones detectados
patterns (id, user_id, type, description, confidence, detected_at)
```

---

## 🚀 5. MVP: Alcance Mínimo Viable (3 meses)

**Objetivo:** Validar la hipótesis central: *¿La gente cambia su comportamiento financiero con un coach que ejecuta y gamifica?*

### Incluir en MVP:

| Prioridad | Funcionalidad | Pilar |
|-----------|---------------|-------|
| 🔴 Alta | Registro manual de transacciones | Base |
| 🔴 Alta | Coach con mensajes motivacionales contextuales (C-01, C-04) | Coach |
| 🔴 Alta | Check-in emocional diario (C-02) | Coach |
| 🔴 Alta | OCR de recibos (A-01) | Automatización |
| 🔴 Alta | Sistema de puntos y niveles (G-03) | Gamificación |
| 🔴 Alta | Metas de ahorro con verificación (G-02) | Gamificación |
| 🟡 Media | Retos personalizados simples (G-01) | Gamificación |
| 🟡 Media | Insignias básicas (G-04) | Gamificación |
| 🟢 Baja | Integración SMS (A-03) | Automatización |
| 🟢 Baja | Wrapped mensual (G-08) | Gamificación |

### **NO incluir en MVP:**
- ❌ Integración Gmail API (por costo CASA)
- ❌ Integración bancaria (Plaid/Belvo)
- ❌ Ligas sociales y competición
- ❌ Ejecución autónoma de acciones
- ❌ Predicción de déficit

---

## 📋 6. Especificaciones de UI/UX

### Pantallas principales

| Pantalla | Descripción | Elementos clave |
|----------|-------------|-----------------|
| **Home / Dashboard** | Resumen del estado financiero + mensaje del coach | Balance, meta activa, reto del día, check-in emocional |
| **Transacciones** | Lista de movimientos | Filtros, búsqueda, agregar manual/OCR |
| **Coach** | Chat con el coach IA | Mensajes motivacionales, sugerencias accionables, historial |
| **Retos** | Retos activos y completados | Progreso, puntos, insignias, ligas |
| **Metas** | Metas de ahorro | Progreso visual, verificación automática |
| **Perfil** | Configuración | Tono del coach, notificaciones, privacidad |

### Principios de diseño

1. **Cero culpa:** Ningún mensaje usa lenguaje negativo o comparativo dañino.
2. **Acción en 1 tap:** Toda sugerencia tiene un botón de acción inmediata.
3. **Progreso visual:** Barras, anillos, animaciones que celebren logros.
4. **Privacidad visible:** Indicadores claros de qué datos se usan y por qué.
5. **Accesibilidad:** Modo oscuro, tipografía grande, contraste alto.

---

## 🔐 7. Privacidad y Seguridad

**Principios:**
- **Privacy-first:** Todos los datos encriptados en tránsito (TLS 1.3) y en reposo (AES-256).
- **Consentimiento explícito:** Cada integración (Gmail, SMS, bancos) requiere permiso granular.
- **Explicabilidad:** La IA explica por qué sugiere cada acción.
- **Control total:** El usuario puede borrar todos sus datos en cualquier momento.
- **Cumplimiento:** GDPR, CCPA, y regulaciones locales de protección de datos.

**Certificaciones objetivo:**
- ISO 27001
- SOC 2 Type II
- Evaluación CASA de Google (si se integra Gmail)

---

## 🗓️ 8. Roadmap por Fases

| Fase | Duración | Entregable |
|------|----------|------------|
| **Fase 0: Setup** | 2 semanas | Repos, CI/CD, diseño de DB, mockups |
| **Fase 1: MVP Core** | 6 semanas | Auth, transacciones, coach básico, OCR |
| **Fase 2: Gamificación** | 4 semanas | Puntos, metas, retos, insignias |
| **Fase 3: Beta cerrada** | 4 semanas | 50 usuarios, feedback, iteración |
| **Fase 4: Lanzamiento** | 2 semanas | App Store + Play Store |
| **Fase 5: Post-lanzamiento** | Continuo | Gmail API, bancos, ligas sociales |

---

## 📊 9. Métricas de Éxito

| Métrica | Objetivo MVP | Objetivo 6 meses |
|---------|--------------|------------------|
| Retención D7 | 40% | 55% |
| Retención D30 | 20% | 35% |
| Transacciones registradas/semana | 10 | 25 |
| Retos completados | 30% | 50% |
| Check-ins emocionales/semana | 3 | 5 |
| NPS | 30 | 50 |

---

## 🛠️ 10. Instrucciones para el Agente de Código

**Al construir esta app, seguir estas directrices:**

1. **Empezar por el MVP** definido en la sección 5. No añadir funcionalidades fuera de alcance sin aprobación.
2. **Arquitectura modular:** Cada pilar (Coach, Gamificación, Automatización) debe ser un módulo independiente en el backend.
3. **API-first:** Diseñar endpoints REST/GraphQL antes de implementar UI.
4. **Testing:** Cobertura mínima del 70% en lógica de negocio.
5. **Documentación:** Cada módulo debe tener README con endpoints, modelos y flujos.
6. **IA responsable:** Implementar guardrails para que el coach nunca dé consejos financieros regulados (inversiones específicas, etc.) sin disclaimers.
7. **Escalabilidad:** Diseñar para 10,000 usuarios iniciales, con posibilidad de escalar a 1M.
8. **Localización:** Soportar español e inglés desde el día 1.
9. **Accesibilidad:** Cumplir WCAG 2.1 AA.
10. **Entrega incremental:** Sprints de 2 semanas con demos funcionales.

---

## 📎 Anexos

### A. Referencias competitivas
- **Noory:** Botón SOS Compra, IA conversacional
- **Wealthii:** Psicología conductual, reducción de estrés
- **Monello:** 5 dimensiones de salud financiera emocional
- **FinPro:** Gamificación con educación
- **Rapunzl:** Competiciones de inversión con becas
- **FinArt / Finma:** OCR de recibos
- **Inveroos:** Wrapped financiero con fotos

### B. Recursos técnicos
- OpenAI GPT-4o API: https://platform.openai.com/docs
- Google Vision API: https://cloud.google.com/vision/docs
- Plaid: https://plaid.com/docs
- Belvo (Latam): https://belvo.com/docs
- Gmail API: https://developers.google.com/gmail/api

### C. Glosario
- **CASA:** Cloud Application Security Assessment (evaluación de seguridad de Google)
- **OCR:** Optical Character Recognition
- **MVP:** Minimum Viable Product
- **NPS:** Net Promoter Score

---

**Fin del documento.**  
*Versión 1.0 — Listo para enviar a agente de código.*