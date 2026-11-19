# Análisis financiero y decisiones de planes (19 de noviembre de 2026)

> Cierra las decisiones que quedaron abiertas en `docs/iteracion-jurado-nov-2026.md` §9. Fuentes: el consumo real
> de IA medido en la tabla `ai_usage`, precios públicos de proveedores (noviembre de 2026) y una réplica en Python
> del plan a 36 meses del Excel. El libro actualizado es
> `docs/negocio/Plantilla_Finanzas_SWNT_PayCheck_36M_v2.xlsx` (el original queda intacto).

## 1. Resumen ejecutivo

| | Antes | Ahora |
|---|---|---|
| Costo de IA por solicitud (cargado) | $3,05 | **$0,80** |
| Costo de IA como % del precio | 7,6 % | **2,0 %** |
| Infraestructura | USD 90/mes | **USD 30/mes** (Render Starter + Neon Launch) |
| Mes de equilibrio | 16 | **14** sin cambiar precios · **12** con la licencia de plataforma |
| Utilidad a 36 meses | $82,8 M | **$128,2 M** · **$254,2 M** con la licencia |
| Ronda que se pide | $163 M | **$115 M** (cubre incluso el escenario pesimista) |
| Filas en "Revisar" del Excel | 3 | **0** |

**Conclusión:** la IA no es el riesgo del negocio (cuesta 2 % del precio). Lo que mueve el equilibrio son los
costos fijos y el canal universitario. Por eso la decisión más rentable es cobrar a la universidad una
**licencia de plataforma** por el panel y los apoyos, no subir precios a los estudiantes ni recortar el plan gratis.

---

## 2. Costo real de la IA

### 2.1 Tokens medidos frente a los estimados

Promedio por llamada exitosa en `ai_usage` (campo `usage` de Groq, incluye razonamiento):

| Tarea | Usos al mes | Entrada medida | Salida medida | Salida que suponía el Excel |
|---|---|---|---|---|
| Registro | 40 | 573 | 98 | 400 |
| Reacción | 60 | 613 | 199 | 1.000 |
| Consejos | 20 | 703 | 185 | 1.200 |
| Chat | 17,25 | 1.335 | 425 | 1.200 |
| Reporte | 8 | 349 | 120 | 500 |
| Resumen mensual | 2 | 579 | 260 | 1.000 |

La salida real es **3 a 6 veces menor** que la estimada. La muestra es pequeña (16 llamadas), así que se mantiene
un factor de seguridad ×1,5 (antes ×2), un 10 % de reintentos y un 10 % de tráfico por el proveedor de respaldo.

### 2.2 Proveedores comparados (mismo uso de una cuenta al mes, sin cargas)

| Modelo y proveedor | USD por millón (entrada / salida) | COP por cuenta al mes | COP por solicitud |
|---|---|---|---|
| gpt-oss-20b en **Groq** (el actual) | 0,075 / 0,30 | 53 | 0,36 |
| gpt-oss-20b en **DeepInfra** | 0,03 / 0,14 | 23 | 0,16 |
| gpt-oss-20b en Fireworks | 0,05 / 0,20 | 35 | 0,24 |
| gpt-oss-20b, piso en OpenRouter | 0,018 / 0,09 | 14 | 0,10 |
| OpenAI GPT-5 nano | 0,05 / 0,40 | 54 | 0,37 |
| Mistral Small 4 | 0,15 / 0,60 | 106 | 0,72 |
| Gemini 3.1 Flash-Lite | 0,25 / 1,50 | 224 | 1,52 |

TRM: $3.300 (TRM certificada del 13 de noviembre: $3.301,91).

**Decisión D9: Groq sigue como principal y DeepInfra entra como respaldo con el mismo modelo.**
- Groq es el más rápido (~850 tokens por segundo), lo que importa en el chat y en la reacción tras registrar. Su
  plan Developer (pago por uso) da 250.000 tokens por minuto, muy por encima del pico estimado para el mes 12
  (~32.000 tokens por minuto con los tokens medidos). El plan gratis (8.000) ya no alcanza.
- DeepInfra cuesta la mitad y sirve **el mismo modelo**: los prompts y los filtros no cambian. Reemplaza el
  supuesto anterior de Gemini como respaldo, que costaba 4 veces más y no existía en el código.
- Pasar todo a DeepInfra ahorraría unos $30 por cuenta al mes (0,5 % del precio): no compensa perder la latencia.
- El piso de OpenRouter es más barato, pero esos proveedores no garantizan disponibilidad ni retención de datos:
  no se usa para datos financieros.
- **Aplicado en el código:** `AI_FALLBACK_URL`, `AI_FALLBACK_API_KEY` y `AI_FALLBACK_MODEL` en
  `backend/app/services/groq_client.py`. Apagado mientras no se configure; cada llamada queda en `ai_usage` como
  `respaldo:…`. Tests en `tests/test_respaldo_ia.py`.

### 2.3 Costo cargado (lo que entra al Excel)

| Concepto | COP al mes |
|---|---|
| Costo directo por cuenta (Groq 90 % + DeepInfra 10 %) | 50 |
| Con reintentos (10 %) y seguridad (×1,5) | 82,5 |
| Por cuenta pagada (factor familia ×1,03) | 85,0 |
| Usuarios gratis que trae cada cuenta pagada (0,83 × 80 solicitudes) | 37,0 |
| **Total por cuenta pagada** | **122,0** |
| **Por solicitud (→ `Inputs!B8`)** | **$0,80** |

---

## 3. Infraestructura

| Opción | USD/mes aprox. | Comentario |
|---|---|---|
| **Render Starter + Neon Launch** (elegida) | **~30** | Gestionado, sin dormirse (el plan gratis de Render tarda ~1 minuto en despertar: inaceptable en la demo y en el piloto); Neon cobra por uso y escala a cero |
| Render Starter + DigitalOcean Managed Postgres | ~22–30 | Base de datos de precio fijo; buena alternativa si Neon sube |
| Railway | ~26–57 | Cobra por uso; más caro para servicios siempre encendidos |
| Fly.io | ~9–19 (sin Postgres gestionado) | El Postgres gestionado parte de USD 38 |
| Hetzner (servidor propio) | ~5–7 | El más barato, pero el equipo tendría que operar el servidor y los respaldos. Opción cuando haya alguien de infraestructura |

El Excel conserva el escalón de infraestructura por cada 3.000 usuarios pagos (`Plan_36M`).

---

## 4. Planes: decisiones

| # | Decisión | Por qué |
|---|---|---|
| D2 | **Gratis mantiene 150 solicitudes de IA al mes** | Un usuario gratis activo cuesta ~$45 al mes con uso típico y $84 si agota el cupo. Cortar el cupo ahorraría centavos y rompería el hábito |
| D7 | **El chat y los reportes quedan en todos los planes** (antes se iban a cerrar en Gratis) | El chat cuesta ~$0,75 por mensaje y los reportes menos. Son lo que crea hábito y lo que se comparte (tarjetas del mes): cerrarlos frena la viralidad sin ahorrar nada |
| — | **Lo que paga cada plan** | Premium: captura automática (notificaciones y SMS) y el doble de IA. Familiar: lo anterior más el progreso compartido. Institucional: lo anterior más los apoyos de la universidad y el panel |
| — | **Precios se mantienen**: Premium $9.990, Familiar $19.990, Institucional $4.998 por estudiante activo (con IVA) | Premium sigue por debajo de la competencia local ($14.500–$20.000) y al nivel de Spotify Estudiante. Subirlo arriesga la conversión (2,18 %) por poco ingreso |
| D8 | **Licencia de plataforma por convenio: $1.190.000 al mes con IVA ($1.000.000 netos)** | Paga el panel de Bienestar, los apoyos y la gestión de códigos. Para una universidad es menos que medio salario de un profesional de bienestar. Es la palanca más grande del modelo (§5) |
| — | **Paquetes extra** se mantienen: Premium 100 solicitudes por $990 y Familiar 200 por $1.490 | Con el costo nuevo dejan ~89 % de margen. El precio mínimo para no perder baja de $427 a $112 |

**Aplicado en el código:** `backend/app/services/planes.py` (funciones por plan), `mobile/.../plan_screen.dart` y
los textos en `app_es.arb` y `app_en.arb`. La licencia de plataforma es una condición comercial y no está en el
código.

---

## 5. Escenarios a 36 meses

Réplica en Python del `Plan_36M` del Excel; reproduce exactamente el libro original (equilibrio en el mes 16,
utilidad de $82,8 M). Detalle también en la hoja `Ajuste_Nov2026` del Excel v2.

| Escenario | Equilibrio | Pérdida máxima | Ronda necesaria | Utilidad 36 meses | Margen año 1 / 2 / 3 |
|---|---|---|---|---|---|
| A. Excel antes del ajuste | mes 16 | $86,9 M | $115 M | $82,8 M | −95,9 % / 13,6 % / 41,6 % |
| B. Costos reales (lo que queda en `Inputs`) | mes 14 | $77,6 M | $105 M | $128,2 M | −87,7 % / 20,7 % / 48,6 % |
| **C. B + licencia de plataforma (recomendado)** | **mes 12** | **$59,9 M** | **$88 M** | **$254,2 M** | −55,8 % / 33,8 % / 57,1 % |
| D. C con crecimiento pesimista (8 / 4 / 2 %) | mes 19 | $83,7 M | $111 M | $16,4 M | −88,9 % / 5,1 % / 33,8 % |
| E. C con la IA 3 veces más cara | mes 12 | $62,9 M | $91 M | $229,0 M | −59,1 % / 30,5 % / 53,8 % |
| F. C sin los usuarios B2C del mes 1 | mes 15 | $79,6 M | $107 M | $111,8 M | −92,2 % / 18,7 % / 47,4 % |

Lectura:
- **La IA no es el riesgo:** triplicar su costo (E) apenas mueve el resultado.
- **El riesgo es el crecimiento (D):** con 8 % mensual se sigue llegando al equilibrio (mes 19), pero la utilidad a
  3 años cae a $16 M. Por eso la ronda se dimensiona para ese caso.
- **La licencia de plataforma adelanta el equilibrio dos meses** y duplica la utilidad a 36 meses.

---

## 6. La ronda

**Decisión: pedir $115 M (antes $163 M).** Cubre la pérdida acumulada máxima del escenario pesimista (D, $83,7 M)
más dos meses de costos fijos ($27,2 M), redondeado. En el escenario recomendado (C) sobran unos $27 M como colchón.
En el Excel: `Supuestos_PayCheck!B75` toma el mayor entre el mínimo del plan base y esta ronda, y `Inputs!B15`
coincide.

---

## 7. Las tres filas en "Revisar" del Excel

| Fila | Antes | Decisión |
|---|---|---|
| Nómina | $13,58 M calculado (contrato laboral) contra $10,5 M escrito | **$10,5 M por prestación de servicios** ($2,1 M por integrante), como dice el documento del modelo. El cálculo laboral queda como referencia |
| Marketing | $1,5 M calculado contra $2 M escrito | **$2 M**: eventos en campus $1 M y pauta y programa de referidos $1 M (las vacas y las tarjetas compartibles hacen que los referidos valgan más) |
| Caja inicial | $120 M calculado contra $163 M escrito | **$115 M** (§6) |

---

## 8. Google Play

| Tema | Lo que dice la política | Decisión |
|---|---|---|
| Comisión | Suscripciones con renovación automática: 15 % (Colombia no aparece en los países con el esquema nuevo; se asume el 15 % vigente) | Se mantiene el 15 % en Premium y Familiar. El Institucional se factura directo, sin tienda |
| `READ_SMS` | Solo para la app de SMS por defecto, salvo excepciones con declaración. Existe una excepción de "gestión de dinero basada en SMS" (aparece como vista previa) | **No pedir `READ_SMS` en la versión de Play.** Además, Play Protect marca como de alto riesgo las apps que combinan SMS con acceso a notificaciones |
| Acceso a notificaciones | No hay formulario de declaración específico, pero exige divulgación destacada y consentimiento antes de pedirlo, y que sea una función central | **Es el canal de captura de la versión de Play.** La app ya muestra el consentimiento antes de abrir los ajustes |

**Para publicar** (fuera del alcance de la demo): quitar `READ_SMS` del `AndroidManifest.xml` de la versión de Play
y ocultar el botón de SMS. Los SMS quedan solo en el APK del piloto. Llenar la sección de Seguridad de los datos con
lo que dice `docs/privacidad.md`.

---

## 9. Pendientes

1. Medir el uso real con más personas en el piloto (`ai_usage`) y, con 200 o más llamadas por tarea, bajar el
   factor de seguridad de ×1,5 a ×1,2.
2. Crear la cuenta de DeepInfra y configurar `AI_FALLBACK_*` en Render.
3. Pasar Render a Starter antes del piloto (hoy está en el plan gratis, que se duerme).
4. Negociar la licencia de plataforma con la ECI en el primer convenio (contrato semestral).
5. Actualizar el documento `Modelo_Financiero_PayCheck_SWNT(1).docx` con estas cifras (este análisis y el Excel v2
   son la fuente).

## Fuentes

- Precios de gpt-oss-20b: [aipricing.guru](https://www.aipricing.guru/models/openai-gpt-oss-20b/), [spendline.ai](https://www.spendline.ai/pricing/groq/groq-gpt-oss-20b/), [pricepertoken.com](https://pricepertoken.com/pricing-page/model/openai-gpt-oss-20b), [Maxim (DeepInfra)](https://www.getmaxim.ai/bifrost/llm-cost-calculator/provider/deepinfra/model/gpt-oss-20b), [CloudPrice](https://cloudprice.net/models/openai/gpt-oss-20b), [ComputePrices (Fireworks)](https://computeprices.com/providers/fireworks-ai/models/gpt-oss-20b)
- Groq y límites: [maximem.ai](https://www.maximem.ai/blog/groq-api-pricing-2026), [eesel.ai](https://www.eesel.ai/de/blog/groq-preise), [usagepricing.com](https://usagepricing.com/blueprint/groq)
- Otros modelos: [aireiter.com](https://aireiter.com/blog/cheapest-llm-api), [benchlm.ai](https://benchlm.ai/blog/posts/llm-pricing-2026), [morphllm.com (Gemini)](https://www.morphllm.com/gemini-api-pricing)
- Hosting: [bex.co](https://bex.co/blog/2026/09/18/railway-render-flyio-pricing-census-hetzner-flat-rate), [expresstech.io](https://expresstech.io/render-vs-railway-vs-fly-io-2026-pricing-showdown/)
- Postgres: [dev.to (10 GB en 7 proveedores)](https://dev.to/myclawnlabs/managed-postgres-with-10-gb-what-it-really-costs-on-7-hosts-n43), [bytebase.com](https://www.bytebase.com/blog/postgres-hosting-options-pricing-comparison/)
- Google Play: [comisiones](https://support.google.com/googleplay/android-developer/answer/112622?hl=en), [Adapty](https://adapty.io/blog/google-play-billing-changes-subscriptions-fees/), [permisos de SMS](https://support.google.com/googleplay/android-developer/answer/10208820?hl=en), [vista previa de la excepción](https://support.google.com/googleplay/android-developer/answer/17225965?hl=en), [divulgación destacada](https://support.google.com/googleplay/android-developer/answer/11150561?hl=en), [Play Protect](https://developers.google.com/android/play-protect/warning-dev-guidance)
- TRM: [Diario del Sur, 13 nov 2026](https://www.diariodelsur.com.co/noticias/dolar-alcanzo-su-nivel-mas-alto-en-mas-de-un-mes-este-13-de-noviembre), [dolar-colombia.com](https://www.dolar-colombia.com/2026-11-11)
