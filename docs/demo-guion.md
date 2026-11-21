# Guion de la demo ante el jurado

> Preparado tras la auditoría del 18 nov 2026. Duración objetivo de la demo en vivo: **3 minutos**. El resto del
> pitch (problema, mercado, modelo financiero) va en las diapositivas.

## 1. Antes de entrar (checklist)

| # | Qué | Cómo |
|---|---|---|
| 1 | Datos de demo frescos | `cd backend && uv run python -m app.db.seed_demo` (idempotente). Anota la URL del panel que imprime. |
| 2 | Backend despierto | Producción (AWS): `https://paycheck-swnt.duckdns.org/health` responde `{"status":"ok"}`. Si se usa Render de respaldo, abrir su `/health` 2 minutos antes (tarda ~1 min en despertar). Si es el PC: `uvicorn app.main:app --host 0.0.0.0 --port 8000` y `adb reverse tcp:8000 tcp:8000`. Checklist completa en [despliegue.md](despliegue.md#antes-de-una-demo). |
| 3 | IA con margen | Groq gratis permite 8.000 tokens por minuto: para la demo, la llave de pago o no repetir el chat muchas veces seguidas. Si la IA cae, la app sigue funcionando con sus textos de respaldo (eso también se puede mostrar). |
| 4 | APK de release | Instalar el del último Release (<https://github.com/PAY-CHECK-SWNT/pay_and_check/releases/latest/download/pay-and-check.apk>, v0.1.3 o posterior). Si el teléfono tiene un APK de depuración, desinstalarlo antes. |
| 4b | Jurados con iPhone | Mostrarles <https://pay-and-check-seven.vercel.app> (Safari → *Agregar a pantalla de inicio*). Misma cuenta y mismos datos; sin recibos, SMS ni recordatorios. |
| 5 | Sesión | Entrar **después** del paso 1 (la semilla recrea las cuentas y cierra cualquier sesión abierta) con **valentina@demo.payandcheck.app / Demo2026!** (plan Institucional por el convenio `ECI-2026`). Del correo a la contraseña, pasar con la tecla «siguiente»: el teclado desplaza el formulario y un toque puede caer en «Crea una». Para mostrar el plan Familiar, en otro teléfono o después: **papa@demo.payandcheck.app / Demo2026!** |
| 5b | Widget | Mantener presionada la pantalla de inicio → Widgets → «Pay & Check: tu día». Abrir la app una vez para que se llene. |
| 6 | Notificaciones | Ajustes → Acceso a notificaciones → activar Pay & Check. Para la notificación de prueba, ver §3, paso 3. |
| 7 | Panel abierto en el portátil | La URL del paso 1, en el navegador del proyector. |
| 8 | Teléfono en «No molestar» | Silenciar WhatsApp y demás apps: durante la prueba entraron mensajes personales sobre la app. |

## 2. La historia en una frase

> «Valentina estudia en la Escuela, vive con $1.400.000 de mesada y nunca sabe si le alcanza. Pay&Check no le
> muestra lo que ya gastó: le dice **antes** de gastar si le alcanza, lo registra solo y, si el mes viene
> difícil, la conecta con los apoyos de su universidad.»

## 3. La demo en vivo (4 minutos)

1. **Widget e Inicio (20 s).** Desde la pantalla de inicio del teléfono: el widget con su número del día. Tocar
   «+ Registrar» abre la app directo en el registro (cerrarla). En Inicio: el número del día, el aviso de que
   este mes viene justo y la tarjeta **«Tu universidad tiene apoyos»**.
2. **¿Me alcanza? (40 s).** Botón en la tarjeta principal → 180.000 para unos tenis → «Tu día baja de X a Y ·
   equivale a N días de ahorro para tu meta». Cambiar a **«A cuotas»**: 1.200.000 a 12 cuotas al 28 % E.A. →
   cuota, intereses y cómo baja el número del día durante un año. **Este es el diferencial:** las demás apps
   cuentan lo que ya pasó; esta ayuda a decidir.
3. **Captura automática (30 s).** Llega una notificación de Nequi (real, o simulada desde el PC):
   `adb shell cmd notification post -t "Nequi" demo "Pagaste \$38.000 en RAPPI"`.
   Campana → Aprobar → la IA ya lo categorizó → Guardar. Cero tecleo.
4. **La vaca (30 s).** Registrar → Formulario manual → 84.000, «Pizza» → «Lo pagué por varias personas»: Juan,
   Laura, Mateo → Guardar. Se abre WhatsApp con el mensaje del cobro. En Inicio: «Te deben $63.000».
5. **Coach que planea (40 s).** Chat: «quiero ahorrar 2 millones para Santa Marta en marzo» → aporte por semana
   calculado por el backend y botón «Crear meta» (en el diálogo, los atajos «Abrir Nequi / Daviplata» para
   guardarlo de verdad). Luego: «escríbeme un poema» → se niega con amabilidad.
6. **Lo que viene y lo que se repite (20 s).** Perfil → Gastos que vienen: regalos de Navidad, «aparta $X por
   semana». Análisis → Gastos que se repiten: tinto diario, Spotify, Netflix, cuánto suman al semestre.
7. **Apoyos y panel (40 s).** Tocar la tarjeta de apoyos → «Me interesa» en el auxilio de alimentación. En el
   portátil, el panel de Bienestar: estudiantes con estrés financiero, presupuestos en riesgo y **cuántos se
   interesaron en cada apoyo**. «Esto es lo que paga la universidad: ver a tiempo el estrés financiero y conectar
   a cada estudiante con la ayuda, sin saber quién es.»
8. **Cierre (10 s).** Mostrar un logro como tarjeta para Instagram (sin montos): así se vuelve viral entre
   estudiantes.

## 4. Preguntas difíciles del jurado (y la respuesta corta)

| Pregunta | Respuesta |
|---|---|
| ¿Por qué no uso los bolsillos de Nequi? | Nequi guarda plata; no te dice si te alcanza. Pay&Check junta Nequi, Daviplata, el banco y el efectivo en un solo número del día, decide contigo antes de gastar y te acompaña sin regañar. Los bolsillos son complemento, no competencia. |
| ¿Cómo evitan que la IA invente cifras? | La IA redacta, no calcula. Toda cifra sale de código determinista (`simulador.py`, `budget_calculator.py`) y un filtro descarta cualquier número que no esté en los datos. Hay pruebas automáticas de eso (`test_coach_cifras.py`). |
| ¿Cuánto les cuesta la IA por usuario? | Lo medimos: cada llamada queda en `ai_usage` con sus tokens. Una solicitud cuesta $0,36 en Groq y $0,80 con respaldo, reintentos y margen de seguridad: unos $122 al mes por cuenta pagada, el 2 % del precio. Tenemos un proveedor de respaldo con el mismo modelo (DeepInfra) por si Groq falla. |
| ¿Cuánto piden y cuándo llegan al equilibrio? | $150 M (antes $163 M; el mínimo es $105 M). Equilibrio en el mes 14 con el plan base y en el 12 con la licencia de plataforma. La ronda alcanza aun creciendo al 8 % y sin la licencia (equilibrio en el mes 23, caja mínima de $28 M). |
| ¿Y la privacidad? | Ley 1581: consentimiento explícito y versionado, los SMS y las notificaciones se leen en el teléfono, borrado total de la cuenta y un panel institucional solo agregado. |
| ¿Y si tengo iPhone? | La misma app corre en el navegador: <https://pay-and-check-seven.vercel.app>, instalable desde Safari. Lo que necesita el teléfono Android (leer SMS, notificaciones del banco, recibos en el dispositivo) se oculta allí. |
| ¿Google Play deja leer SMS? | Play restringe `READ_SMS`. Por eso la captura principal es por notificaciones (`NotificationListenerService`), que es como llegan los pagos de Nequi y Daviplata; los SMS quedan como respaldo para la distribución por APK. |
| ¿Por qué pagaría la universidad? | Porque recibe el panel de bienestar financiero y es un beneficio para sus estudiantes a $4.998 por estudiante activo, la mitad del Premium. |
| ¿Qué los diferencia de Bankity o MonAi? | La captura y el dictado son requisito básico; el diferencial es decidir antes de gastar (contado y cuotas), el coach que no inventa cifras y el canal universitario con apoyos y panel. |
| ¿Y el plan Familiar? | Los papás ven el progreso agregado del hijo que decide compartirlo (racha, metas, si le alcanza), nunca sus gastos. |
| ¿Qué sigue? | Recompensas con comercios del campus, retos entre amigos, presupuesto alineado a la fecha de la mesada, lectura de correos del banco y la publicación en Google Play. |

## 5. Si algo falla en vivo

- **La IA no responde:** el registro cae al formulario manual y el coach usa sus textos de respaldo. Decirlo: «así
  está diseñado».
- **Backend dormido:** abrir `/health` y seguir con las diapositivas mientras despierta.
- **No llega la notificación:** repetir el comando `adb` del paso 3, o mostrar la bandeja de SMS.
