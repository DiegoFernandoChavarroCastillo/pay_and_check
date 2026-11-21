# ADR-007 · Distribución por APK en el piloto, Google Play después

- **Estado:** aceptada
- **Fecha:** 2026-11-18

## Contexto

La app es Flutter para Android. Publicar en Google Play exige cuenta de desarrollador, revisión, ficha de la
tienda y, en particular, justificar el permiso `READ_SMS`, que la app declara para leer los SMS del banco
([`mobile/android/app/src/main/AndroidManifest.xml`](../../mobile/android/app/src/main/AndroidManifest.xml)).
Google restringe ese permiso y su aprobación no se controla en los tiempos del piloto
(HU-038 en Jira).

## Decisión

- En el piloto la app se distribuye como **APK firmado adjunto a un GitHub Release**.
- [`.github/workflows/mobile-release.yml`](../../.github/workflows/mobile-release.yml): al empujar un tag `v*`
  restaura el keystore desde secretos, corre `flutter test`, compila con `--dart-define=API_BASE_URL` y
  `GOOGLE_SERVER_CLIENT_ID`, y publica `pay-and-check-<tag>.apk` en el Release.
- La firma usa siempre el mismo keystore (secreto `ANDROID_KEYSTORE_BASE64`); el workflow falla si falta. Sin él,
  cada build saldría con una llave de depuración distinta y no podría actualizar al anterior
  ([`mobile/android/app/build.gradle.kts`](../../mobile/android/app/build.gradle.kts)).
- La URL del backend se fija al compilar ([`mobile/lib/core/config/app_config.dart`](../../mobile/lib/core/config/app_config.dart)).

## Alternativas consideradas

- **Google Play (prueba interna o cerrada).** Es el paso siguiente (HU-038, pendiente). Requiere migrar a App
  Bundle y la declaración de `READ_SMS`.
- **Firebase App Distribution.** No se evaluó en el repo.

## Consecuencias

- Las personas del piloto instalan desde un enlace y deben permitir "orígenes desconocidos".
- No hay actualizaciones automáticas: cada versión es un APK nuevo que hay que reinstalar.
- Sin tienda no hay Google Play Billing: los planes de pago son simulados ([ADR-008](008-planes-simulados-cupo-ia.md)).
- El APK apunta a una sola `API_BASE_URL`: cambiar de backend exige recompilar.
