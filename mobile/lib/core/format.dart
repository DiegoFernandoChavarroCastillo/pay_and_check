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
String errorMessage(Object error, AppLocalizations l) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map && data['detail'] is String) return data['detail'] as String;
    if (error.response?.statusCode == 422) return l.errorInvalidData;
    if (error.response == null) return l.errorNetwork;
  }
  return l.errorGeneric;
}
