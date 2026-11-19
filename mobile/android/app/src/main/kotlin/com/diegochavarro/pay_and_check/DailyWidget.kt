package com.diegochavarro.pay_and_check

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

/**
 * Widget de la pantalla de inicio: el número del día ("$43.243 hoy") sin abrir la app, y un botón para
 * registrar un gasto. La app escribe el texto con [guardar] cada vez que carga el resumen; el widget no habla
 * con el servidor.
 */
class DailyWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        for (id in ids) manager.updateAppWidget(id, vista(context))
    }

    companion object {
        private const val PREFS = "daily_widget"
        const val ACCION_REGISTRAR = "registrar"
        const val EXTRA_ACCION = "accion"

        fun guardar(context: Context, monto: String, etiqueta: String, detalle: String) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString("monto", monto).putString("etiqueta", etiqueta).putString("detalle", detalle).apply()
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, DailyWidget::class.java))
            for (id in ids) manager.updateAppWidget(id, vista(context))
        }

        private fun abrir(context: Context, accion: String?, codigo: Int): PendingIntent {
            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                if (accion != null) putExtra(EXTRA_ACCION, accion)
            }
            return PendingIntent.getActivity(
                context, codigo, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }

        private fun vista(context: Context): RemoteViews {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            return RemoteViews(context.packageName, R.layout.daily_widget).apply {
                setTextViewText(R.id.widget_monto, prefs.getString("monto", "—"))
                setTextViewText(R.id.widget_etiqueta, prefs.getString("etiqueta", "Disponible hoy"))
                setTextViewText(R.id.widget_detalle, prefs.getString("detalle", "Abre Pay & Check para actualizar"))
                setOnClickPendingIntent(R.id.widget_raiz, abrir(context, null, 1))
                setOnClickPendingIntent(R.id.widget_registrar, abrir(context, ACCION_REGISTRAR, 2))
            }
        }
    }
}
