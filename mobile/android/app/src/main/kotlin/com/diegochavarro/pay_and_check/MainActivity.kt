package com.diegochavarro.pay_and_check

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import android.provider.Telephony
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Además de alojar Flutter, expone el canal "pay_and_check/sms": lectura de la
 * bandeja de SMS y de las notificaciones de apps de pago guardadas por
 * [BankNotificationListener] para detectar movimientos bancarios. Solo lee cuando el
 * usuario abre esa función y concede el permiso; los mensajes se devuelven a
 * la app y es ella la que decide cuáles mostrar.
 */
class MainActivity : FlutterActivity() {
    private var pendingPermission: MethodChannel.Result? = null

    /** Lo que pidió el widget al abrir la app ("registrar"), hasta que Flutter lo lea. */
    private var accionPendiente: String? = null

    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        accionPendiente = intent?.getStringExtra(DailyWidget.EXTRA_ACCION)
        super.onCreate(savedInstanceState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getStringExtra(DailyWidget.EXTRA_ACCION)?.let { accion ->
            accionPendiente = accion
            flutterEngine?.dartExecutor?.binaryMessenger?.let {
                MethodChannel(it, CHANNEL).invokeMethod("widgetAction", accion)
            }
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "hasPermission" -> result.success(hasPermission())
                "requestPermission" -> requestPermission(result)
                "readInbox" -> {
                    val since = call.argument<Number>("since")?.toLong() ?: 0L
                    if (hasPermission()) result.success(readInbox(since))
                    else result.error("no_permission", "READ_SMS no concedido", null)
                }
                "notifHasAccess" -> result.success(notifHasAccess())
                "openNotifSettings" -> {
                    startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    result.success(null)
                }
                "paymentApps" -> result.success(
                    APPS_DE_PAGO.filterKeys { packageManager.getLaunchIntentForPackage(it) != null }
                        .map { mapOf("package" to it.key, "nombre" to it.value) },
                )
                "openApp" -> {
                    val intent = call.argument<String>("package")
                        ?.takeIf { it in APPS_DE_PAGO }
                        ?.let { packageManager.getLaunchIntentForPackage(it) }
                    if (intent != null) startActivity(intent)
                    result.success(intent != null)
                }
                "updateWidget" -> {
                    DailyWidget.guardar(
                        this,
                        call.argument<String>("monto").orEmpty(),
                        call.argument<String>("etiqueta").orEmpty(),
                        call.argument<String>("detalle").orEmpty(),
                    )
                    result.success(null)
                }
                "launchAction" -> {
                    // Se lee una sola vez: si no, cada vuelta a la app reabriría la hoja de registro.
                    result.success(accionPendiente)
                    accionPendiente = null
                }
                "readNotifications" -> {
                    val since = call.argument<Number>("since")?.toLong() ?: 0L
                    result.success(if (notifHasAccess()) BankNotificationListener.leer(this, since) else emptyList())
                }
                else -> result.notImplemented()
            }
        }
    }

    /** Si la persona activó "Pay & Check" en Ajustes → Acceso a notificaciones. */
    private fun notifHasAccess(): Boolean {
        val activos = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
        val nuestro = ComponentName(this, BankNotificationListener::class.java).flattenToString()
        return activos.split(":").any { it == nuestro }
    }

    private fun hasPermission() =
        checkSelfPermission(Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED

    private fun requestPermission(result: MethodChannel.Result) {
        if (hasPermission()) return result.success(true)
        // Una sola solicitud a la vez: si quedó otra pendiente, se da por denegada.
        pendingPermission?.success(false)
        pendingPermission = result
        requestPermissions(arrayOf(Manifest.permission.READ_SMS), REQUEST_SMS)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQUEST_SMS) return
        pendingPermission?.success(grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED)
        pendingPermission = null
    }

    private fun readInbox(since: Long): List<Map<String, Any?>> {
        val messages = mutableListOf<Map<String, Any?>>()
        contentResolver.query(
            Telephony.Sms.Inbox.CONTENT_URI,
            arrayOf(Telephony.Sms._ID, Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE),
            "${Telephony.Sms.DATE} >= ?",
            arrayOf(since.toString()),
            "${Telephony.Sms.DATE} DESC",
        )?.use { cursor ->
            while (cursor.moveToNext() && messages.size < MAX_MESSAGES) {
                messages.add(
                    mapOf(
                        "id" to cursor.getLong(0),
                        "address" to cursor.getString(1),
                        "body" to cursor.getString(2),
                        "date" to cursor.getLong(3),
                    ),
                )
            }
        }
        return messages
    }

    private companion object {
        const val CHANNEL = "pay_and_check/sms"
        const val REQUEST_SMS = 4201
        const val MAX_MESSAGES = 300

        /** Las únicas apps que la app abre ("Apartar en Nequi"); deben estar en <queries> del manifest. */
        val APPS_DE_PAGO = mapOf(
            "com.nequi.MobileApp" to "Nequi",
            "com.davivienda.daviplataapp" to "Daviplata",
            "co.com.bancolombia.personas.superapp" to "Bancolombia",
            "com.nu.production" to "Nu",
        )
    }
}
