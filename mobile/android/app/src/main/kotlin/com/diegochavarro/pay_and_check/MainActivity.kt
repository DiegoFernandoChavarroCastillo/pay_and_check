package com.diegochavarro.pay_and_check

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Telephony
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Además de alojar Flutter, expone el canal "pay_and_check/sms": lectura de la
 * bandeja de SMS para detectar movimientos bancarios. Solo lee cuando el
 * usuario abre esa función y concede el permiso; los mensajes se devuelven a
 * la app y es ella la que decide cuáles mostrar.
 */
class MainActivity : FlutterActivity() {
    private var pendingPermission: MethodChannel.Result? = null

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
                else -> result.notImplemented()
            }
        }
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
    }
}
