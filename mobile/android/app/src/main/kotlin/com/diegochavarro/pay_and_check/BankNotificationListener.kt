package com.diegochavarro.pay_and_check

import android.app.Notification
import android.content.Context
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject

/**
 * Guarda en el teléfono las notificaciones de las apps de pago y bancos (Nequi, Daviplata, Bancolombia, Nu…)
 * para que la app proponga esos movimientos en la misma bandeja que los SMS. Solo escucha si la persona le dio
 * acceso en Ajustes, solo mira los paquetes de [BANCOS] y nada sale del teléfono: la app lee esta lista cuando
 * se abre la bandeja, y cada movimiento se confirma a mano antes de guardarse.
 */
class BankNotificationListener : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val banco = BANCOS[sbn.packageName] ?: return
        val extras = sbn.notification.extras
        val titulo = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val texto = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
            ?: extras.getCharSequence(Notification.EXTRA_TEXT))?.toString().orEmpty()
        if (texto.isBlank()) return
        guardar(applicationContext, sbn.postTime, banco, titulo, texto)
    }

    companion object {
        private const val PREFS = "bank_notifications"
        private const val KEY = "items"
        private const val MAX = 300

        /** Paquete → nombre que se muestra como remitente. `com.android.shell` permite probar con
         *  `adb shell cmd notification post`. */
        val BANCOS = mapOf(
            "com.nequi.MobileApp" to "Nequi",
            "com.davivienda.daviplataapp" to "Daviplata",
            "com.davivienda.daviviendaapp" to "Davivienda",
            "co.com.bancolombia.personas.superapp" to "Bancolombia",
            "com.todo1.mobile" to "Bancolombia",
            "com.nu.production" to "Nu",
            "com.lulobank.app" to "Lulo Bank",
            "co.com.bbva.mb" to "BBVA",
            "com.android.shell" to "Prueba",
        )

        @Synchronized
        fun guardar(context: Context, fecha: Long, banco: String, titulo: String, texto: String) {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val actuales = JSONArray(prefs.getString(KEY, "[]"))
            val cuerpo = if (titulo.isBlank() || texto.contains(titulo)) texto else "$titulo. $texto"
            // Una misma notificación se actualiza varias veces: no se duplica.
            for (i in 0 until actuales.length()) {
                val o = actuales.getJSONObject(i)
                if (o.getString("body") == cuerpo && o.getString("address") == banco) return
            }
            val nuevas = JSONArray()
            nuevas.put(JSONObject().put("id", fecha).put("address", banco).put("body", cuerpo).put("date", fecha))
            for (i in 0 until minOf(actuales.length(), MAX - 1)) nuevas.put(actuales.get(i))
            prefs.edit().putString(KEY, nuevas.toString()).apply()
        }

        fun leer(context: Context, desde: Long): List<Map<String, Any?>> {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val items = JSONArray(prefs.getString(KEY, "[]"))
            return (0 until items.length()).map { items.getJSONObject(it) }
                .filter { it.getLong("date") >= desde }
                .map {
                    mapOf(
                        "id" to it.getLong("id"),
                        "address" to it.getString("address"),
                        "body" to it.getString("body"),
                        "date" to it.getLong("date"),
                    )
                }
        }
    }
}
