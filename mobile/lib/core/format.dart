import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart';
import 'package:intl/intl.dart';

import '../l10n/gen/app_localizations.dart';

final _miles = NumberFormat.decimalPattern('es_CO');

/// Monto sin decimales y con punto de miles: `$ 12.500`.
String money(num valor) => '\$ ${_miles.format(valor.round())}';

/// Convierte lo que el usuario escribe ("12.500", "12500", "12,5") en número.
/// Devuelve null si no es un monto positivo.
double? parseMoney(String texto) {
  final limpio = texto.replaceAll(RegExp(r'[^\d,]'), '').replaceAll(',', '.');
  final valor = double.tryParse(limpio);
  return valor == null || valor <= 0 ? null : valor;
}

String shortDate(BuildContext context, DateTime fecha) =>
    DateFormat.MMMd(Localizations.localeOf(context).toLanguageTag()).format(fecha);

String longDate(BuildContext context, DateTime fecha) =>
    DateFormat.yMMMMEEEEd(Localizations.localeOf(context).toLanguageTag()).format(fecha);

String monthName(BuildContext context, int anio, int mes) =>
    DateFormat.yMMMM(Localizations.localeOf(context).toLanguageTag()).format(DateTime(anio, mes));

/// Nombres de los días empezando en lunes (0), como los usa la API.
List<String> weekdayNames(BuildContext context) {
  final nombres = DateFormat.EEEE(Localizations.localeOf(context).toLanguageTag()).dateSymbols.WEEKDAYS;
  return [...nombres.skip(1), nombres.first];
}

DateTime today() {
  final ahora = DateTime.now();
  return DateTime(ahora.year, ahora.month, ahora.day);
}

/// Mensaje legible para un error de red o de la API.
/// El registro con IA no está disponible: 402 si se agotó el cupo del mes y 503 si
/// la IA está caída o limitada (docs/planes.md §4). La app lleva entonces al
/// formulario manual, que no usa IA.
bool esSinIA(Object error) =>
    error is DioException && (error.response?.statusCode == 402 || error.response?.statusCode == 503);

/// El primer monto de un texto ("almuerzo 12.500", "compra por $45.900"), sin IA,
/// para adelantar el formulario manual. Punto o coma seguidos de 3 dígitos son
/// separadores de miles, como en los SMS de los bancos colombianos.
double? montoDelTexto(String texto) {
  final m = RegExp(r'\d{1,3}(?:[.,]\d{3})+|\d+').firstMatch(texto);
  if (m == null) return null;
  final valor = double.tryParse(m.group(0)!.replaceAll(RegExp(r'[.,]'), ''));
  return valor == null || valor <= 0 ? null : valor;
}

String errorMessage(Object error, AppLocalizations l) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map && data['detail'] is String) return data['detail'] as String;
    // Validaciones propias del backend ("Esa contraseña es muy fácil de adivinar…") llegan como la lista de
    // errores de FastAPI con el prefijo "Value error, ": se muestra el mensaje, que ya está escrito para la persona.
    if (data is Map && data['detail'] is List) {
      for (final e in data['detail'] as List) {
        final msg = e is Map ? e['msg'] : null;
        if (msg is String && msg.startsWith('Value error, ')) return msg.substring('Value error, '.length);
      }
    }
    if (error.response?.statusCode == 422) return l.errorInvalidData;
    if (error.response == null) return l.errorNetwork;
  }
  return l.errorGeneric;
}

/// Las categorías por defecto viven en la base con su nombre en español ("comida", "transporte"…) y así las
/// usan la IA y los colores. En inglés solo cambia lo que se muestra; las propias se muestran tal cual.
const _categoriasEn = {
  'comida': 'Food',
  'transporte': 'Transport',
  'entretenimiento': 'Entertainment',
  'salud': 'Health',
  'servicios': 'Utilities',
  'otros': 'Other',
  'compras': 'Shopping',
  'estudio': 'Education',
  'vivienda': 'Housing',
  'deudas': 'Debt',
};

String catLabel(BuildContext context, String nombre) =>
    Localizations.localeOf(context).languageCode == 'en' ? (_categoriasEn[nombre] ?? nombre) : nombre;
