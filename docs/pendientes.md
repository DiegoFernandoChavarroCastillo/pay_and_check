# Pendientes

Lo que falta, al 21 nov 2026, después de la prueba de punta a punta en el teléfono, sus arreglos (PR #5), la
versión web (PR #6 y #7) y la publicación de la v0.1.3. Los pendientes de negocio de la iteración anterior siguen
en [iteracion-jurado-nov-2026.md §11](iteracion-jurado-nov-2026.md#11-pendientes-y-decisiones-abiertas).

## Antes de la presentación

| # | Qué | Por qué | Quién |
|---|---|---|---|
| 1 | Probar la versión web en un **iPhone real** (Safari): agregar a pantalla de inicio, login con correo y con Google, dictado por voz, registrar un gasto | Nadie la ha abierto en iOS. La ventana de Google y el dictado dependen de Safari | Equipo |
| 2 | Confirmar que la **pantalla de consentimiento de Google** está *En producción* | En *Prueba*, solo entran con Google los correos de la lista | Quien administra Google Cloud |
| 3 | Instalar la **v0.1.3** en los teléfonos de la demo y repasar el [guion](demo-guion.md) con ella | El guion se escribió sobre la v0.1.x anterior; el logo, «Ya lo pagué» y la edición de ingresos cambiaron | Equipo |
| 4 | Actualizar el guion: el paso 2 del checklist asume Render o el PC, y el 4 compila el APK a mano | Hoy el backend es AWS y el APK sale del Release | Equipo |

## Producto

| # | Qué | Detalle |
|---|---|---|
| 5 | Un gasto grande planeado (matrícula) baja el ritmo diario como si fuera un gasto normal | Al pagarlo con «Ya lo pagué → Registrarlo ahora», el gasto entra al disponible por día y puede encender el aviso de riesgo. Hace falta enlazar el gasto con su previsto (migración) para excluirlo del ritmo. Ver [reglas-calculo.md §6](reglas-calculo.md) |
| 6 | Google Sign-In en la web no se ha probado en iPhone | Ver #1 |
| 7 | En el PC, la rueda del mouse no desplaza cuando el cursor está en los márgenes vacíos | Efecto de centrar el contenido (`ContenidoCentrado`). Menor |

## Operación

| # | Qué | Detalle |
|---|---|---|
| 8 | Documentar cómo se instaló el backend en AWS | Docker o systemd, ruta, archivo de variables, Caddyfile, *security group*. Va en [despliegue.md](despliegue.md#backend-en-aws) |
| 9 | Rotar las credenciales que se compartieron por chat durante la configuración | Contraseña de la base (Neon), llave de Groq y token de Jira. Después, actualizar el servidor y los secretos de GitHub |
| 10 | Decidir qué hace `keep-alive.yml` | Hoy llama a AWS (por `API_BASE_URL`), así que Render duerme. Si Render debe estar listo como respaldo, apuntar el cron a su URL |
| 11 | Borrar el cliente OAuth web sin uso (`…iauvmenob…`) | Se creó al configurar Google en la web; la web usa el mismo cliente que Android |
| 12 | Variables `AI_FALLBACK_*` (proveedor de IA de respaldo) en el servidor de AWS | Estaban previstas para Render (iteración anterior, #6) |

## Gestión

| # | Qué | Detalle |
|---|---|---|
| 13 | Actualizar Jira con los PR #5, #6 y #7 | Los 22 hallazgos de la prueba en el teléfono, la versión web y el diseño adaptable no tienen tickets. Se dejó para después a pedido del equipo |
| 14 | Regenerar `architecture.pdf` | Es anterior a la versión web y al despliegue en AWS |
| 15 | Actualizar la **política de privacidad** | Dice que la API está en Render; hoy está en AWS. Tampoco menciona la versión web (sesión en el navegador, dictado del navegador). El texto vive en `docs/privacidad.md` **y** en la app (`privacy_policy.dart`) y deben cambiar juntos. Hay que decidir si se sube `POLITICA_VERSION`, lo que obliga a cada cuenta a aceptarla de nuevo |

## Deuda técnica conocida

- `mobile/tool/gen_arb.py` quedó desactualizado: más de 180 claves solo existen en los `.arb`. **No ejecutarlo**
  (aviso en [mobile/README.md](../mobile/README.md#textos-y-traducciones)).
- Riesgos abiertos de seguridad R1 a R3 en [seguridad.md](seguridad.md#riesgos-abiertos-hallazgos-de-otros-tickets).
- Diferencias entre los ADR y el código, en [decisiones/README.md](decisiones/README.md#diferencias-entre-el-plan-y-el-código).
- Google Play: la versión de tienda no pedirá `READ_SMS`; falta preparar el App Bundle y la ficha
  ([ADR-007](decisiones/007-distribucion-apk.md)).
