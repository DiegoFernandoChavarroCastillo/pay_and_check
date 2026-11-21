# Trabajo pendiente

Estado al 21 nov 2026, con la versión **v0.1.3** publicada (APK y web). Los números son solo para referirse a cada
punto; el seguimiento se hace en Jira.

## Calidad y verificación

| # | Qué | Detalle |
|---|---|---|
| 1 | Probar la versión web en un **iPhone real** (Safari) | Agregar a pantalla de inicio, login con correo y con Google, dictado por voz y registrar un gasto. No se ha probado en iOS; la ventana de Google y el dictado dependen de Safari |
| 2 | Confirmar que la **pantalla de consentimiento de Google** está *En producción* | En *Prueba* solo pueden entrar con Google los correos de la lista de usuarios de prueba |
| 3 | Completar la prueba en dispositivo de las funciones más nuevas | Widget, compartir una vaca por WhatsApp, el chat que crea una meta y el plan Familiar visto por el titular |

## Producto

| # | Qué | Detalle |
|---|---|---|
| 4 | Un gasto grande previsto (matrícula) baja el ritmo diario como un gasto normal | Al pagarlo con «Ya lo pagué → Registrarlo ahora», el gasto entra al disponible por día y puede encender el aviso de riesgo. Hace falta enlazar el gasto con su previsto (migración) para excluirlo del ritmo. Ver [reglas-calculo.md §6](reglas-calculo.md) |
| 5 | En el computador, la rueda del mouse no desplaza con el cursor en los márgenes vacíos | Efecto de centrar el contenido (`ContenidoCentrado`). Menor |
| 6 | Hoja de ruta | Recompensas con comercios del campus, retos entre amigos, presupuesto alineado a la fecha de la mesada y lectura de correos del banco |

## Operación

| # | Qué | Detalle |
|---|---|---|
| 7 | Documentar la instalación del backend en AWS | Docker o systemd, ruta del repo, archivo de variables, Caddyfile y *security group*. Va en [despliegue.md](despliegue.md#backend-en-aws) |
| 8 | Rotar las credenciales expuestas durante la configuración inicial | Contraseña de la base (Neon), llave de Groq y token de Jira. Después, actualizar el servidor y los secretos de GitHub |
| 9 | Decidir qué vigila `keep-alive.yml` | Hoy llama a AWS (por `API_BASE_URL`), así que Render duerme. Si Render debe estar listo como respaldo, apuntar el cron a su URL |
| 10 | Configurar `AI_FALLBACK_*` (proveedor de IA de respaldo) en AWS | Sin él, si Groq falla el coach usa sus textos fijos |
| 11 | Borrar el cliente OAuth web sin uso (`…iauvmenob…`) | La web usa el mismo cliente que Android |

## Legal y negocio

| # | Qué | Detalle |
|---|---|---|
| 12 | Actualizar la **política de privacidad** | Dice que la API está en Render y presenta Pay&Check como proyecto académico; tampoco menciona la versión web (sesión en el navegador, dictado del navegador). El texto vive en [privacidad.md](privacidad.md) **y** en la app (`privacy_policy.dart`) y deben cambiar juntos. Hay que decidir si se sube `POLITICA_VERSION`, que obliga a cada cuenta a aceptarla de nuevo |
| 13 | Validar con Bienestar Universitario de la ECI los apoyos reales y el texto de consentimiento del convenio | |
| 14 | Negociar la licencia de plataforma con la ECI y actualizar el modelo financiero | [negocio/](negocio/) |
| 15 | Registrar en Jira el trabajo de los PR #5 a #9 | Hallazgos de la prueba en dispositivo, versión web, diseño adaptable y documentación |

## Deuda técnica conocida

- `mobile/tool/gen_arb.py` quedó desactualizado: más de 180 claves solo existen en los `.arb`. **No ejecutarlo**
  (aviso en [mobile/README.md](../mobile/README.md#textos-y-traducciones)).
- Riesgos abiertos de seguridad R1 a R3 en [seguridad.md](seguridad.md#riesgos-abiertos-hallazgos-de-otros-tickets).
- Diferencias entre los ADR y el código, en [decisiones/README.md](decisiones/README.md#diferencias-entre-el-plan-y-el-código).
- Google Play: la versión de tienda no pedirá `READ_SMS`; falta preparar el App Bundle y la ficha
  ([ADR-007](decisiones/007-distribucion-apk.md), [negocio/analisis-financiero.md §8](negocio/analisis-financiero.md)).
