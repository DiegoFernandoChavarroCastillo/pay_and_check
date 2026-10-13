/// Modelos de la API. Los montos llegan como texto decimal ("5000.00") y las
/// fechas como "YYYY-MM-DD"; aquí se convierten una sola vez.
library;

double _num(dynamic v) => v == null ? 0 : double.parse(v.toString());
double? _numOrNull(dynamic v) => v == null ? null : double.parse(v.toString());
DateTime _date(dynamic v) => DateTime.parse(v as String);
DateTime? _dateOrNull(dynamic v) => v == null ? null : DateTime.parse(v as String);
List<T> _list<T>(dynamic v, T Function(Map<String, dynamic>) f) =>
    (v as List).map((e) => f(e as Map<String, dynamic>)).toList();

/// Fecha sin hora en el formato que espera la API.
String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class User {
  User.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        email = j['email'] as String,
        nombre = j['nombre'] as String,
        coachTone = j['coach_tone'] as String,
        idioma = j['idioma'] as String,
        zonaHoraria = j['zona_horaria'] as String;

  final int id;
  final String email;
  final String nombre;
  final String coachTone;
  final String idioma;
  final String zonaHoraria;
}

class Budget {
  Budget.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        montoTotal = _num(j['monto_total']),
        fechaInicio = _date(j['fecha_inicio']),
        fechaFin = _date(j['fecha_fin']);

  final int id;
  final double montoTotal;
  final DateTime fechaInicio;
  final DateTime fechaFin;
}

class CategoryBreakdown {
  CategoryBreakdown.fromJson(Map<String, dynamic> j)
      : categoria = j['categoria'] as String,
        tipo = j['tipo'] as String,
        gastado = _num(j['gastado']),
        limite = _numOrNull(j['limite']),
        excedido = j['excedido'] as bool;

  final String categoria;
  final String tipo;
  final double gastado;
  final double? limite;
  final bool excedido;
}

class BudgetSummary {
  BudgetSummary.fromJson(Map<String, dynamic> j)
      : budget = Budget.fromJson(j['budget'] as Map<String, dynamic>),
        gastadoTotal = _num(j['gastado_total']),
        ingresosTotal = _num(j['ingresos_total']),
        apartadoTotal = _num(j['apartado_total']),
        disponibleTotal = _num(j['disponible_total']),
        diasRestantes = j['dias_restantes'] as int,
        disponiblePorDia = _num(j['disponible_por_dia']),
        disponiblePorSemana = _num(j['disponible_por_semana']),
        enRiesgo = j['en_riesgo'] as bool,
        fechaAgotamiento = _dateOrNull(j['fecha_proyectada_agotamiento']),
        desglose = _list(j['desglose_por_categoria'], CategoryBreakdown.fromJson);

  final Budget budget;
  final double gastadoTotal;
  final double ingresosTotal;
  final double apartadoTotal;
  final double disponibleTotal;
  final int diasRestantes;
  final double disponiblePorDia;
  final double disponiblePorSemana;
  final bool enRiesgo;
  final DateTime? fechaAgotamiento;
  final List<CategoryBreakdown> desglose;
}

class Category {
  Category.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        nombre = j['nombre'] as String,
        esPropia = j['owner_id'] != null,
        tipo = j['tipo'] as String,
        limite = _numOrNull(j['limite']);

  final int id;
  final String nombre;

  /// Las categorías por defecto son compartidas y no se pueden editar.
  final bool esPropia;
  final String tipo;
  final double? limite;
}

class Expense {
  Expense.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        categoryId = j['category_id'] as int,
        monto = _num(j['monto']),
        descripcion = j['descripcion'] as String,
        source = j['source'] as String,
        comercio = j['comercio'] as String?,
        fecha = _date(j['fecha']);

  final int id;
  final int categoryId;
  final double monto;
  final String descripcion;
  final String source;
  final String? comercio;
  final DateTime fecha;
}

class Income {
  Income.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        monto = _num(j['monto']),
        descripcion = j['descripcion'] as String,
        fecha = _date(j['fecha']);

  final int id;
  final double monto;
  final String descripcion;
  final DateTime fecha;
}

class RecurringExpense {
  RecurringExpense.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        categoryId = j['category_id'] as int,
        monto = _num(j['monto']),
        descripcion = j['descripcion'] as String,
        diaSemana = j['dia_semana'] as int,
        activo = j['activo'] as bool;

  final int id;
  final int categoryId;
  final double monto;
  final String descripcion;
  final int diaSemana;
  final bool activo;
}

/// Borrador de gasto: lo que devuelve la IA al parsear un texto o un recibo,
/// o lo que se precarga al editar. Siempre pasa por confirmación del usuario.
class ExpenseDraft {
  ExpenseDraft({
    this.monto,
    this.categoria,
    this.descripcion,
    this.fecha,
    this.comercio,
    this.source = 'manual',
    this.textoOriginal,
  });

  ExpenseDraft.fromParse(Map<String, dynamic> j, {required this.source, this.textoOriginal})
      : monto = _num(j['monto']),
        categoria = j['categoria'] as String?,
        descripcion = j['descripcion'] as String?,
        fecha = _dateOrNull(j['fecha']),
        comercio = j['comercio'] as String?;

  final double? monto;
  final String? categoria;
  final String? descripcion;
  final DateTime? fecha;
  final String? comercio;
  final String source;
  final String? textoOriginal;
}

class Checkin {
  Checkin.fromJson(Map<String, dynamic> j)
      : fecha = _date(j['fecha']),
        animo = j['animo'] as String,
        nota = j['nota'] as String?;

  final DateTime fecha;
  final String animo;
  final String? nota;
}

class InsightAction {
  InsightAction.fromJson(Map<String, dynamic> j)
      : tipo = j['tipo'] as String,
        etiqueta = j['etiqueta'] as String,
        payload = j['payload'] as Map<String, dynamic>;

  final String tipo;
  final String etiqueta;
  final Map<String, dynamic> payload;
}

class Insight {
  Insight.fromJson(Map<String, dynamic> j)
      : tipo = j['tipo'] as String,
        mensaje = j['mensaje'] as String,
        descripcion = j['descripcion'] as String,
        accion = j['accion'] == null ? null : InsightAction.fromJson(j['accion'] as Map<String, dynamic>);

  final String tipo;
  final String mensaje;

  /// El dato en que se basa el consejo (explicabilidad).
  final String descripcion;
  final InsightAction? accion;
}

class ChatMessage {
  ChatMessage.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        esDelCoach = j['rol'] == 'coach',
        contenido = j['contenido'] as String;

  ChatMessage.local(this.contenido)
      : id = -1,
        esDelCoach = false;

  final int id;
  final bool esDelCoach;
  final String contenido;
}

class Contribution {
  Contribution.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        monto = _num(j['monto']),
        fecha = _date(j['fecha']);

  final int id;
  final double monto;
  final DateTime fecha;
}

class Goal {
  Goal.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        nombre = j['nombre'] as String,
        montoObjetivo = _num(j['monto_objetivo']),
        fechaLimite = _dateOrNull(j['fecha_limite']),
        cumplida = j['estado'] == 'cumplida',
        aportado = _num(j['aportado']),
        progreso = _num(j['progreso']),
        aportes = _list(j['aportes'], Contribution.fromJson);

  final int id;
  final String nombre;
  final double montoObjetivo;
  final DateTime? fechaLimite;
  final bool cumplida;
  final double aportado;
  final double progreso;
  final List<Contribution> aportes;
}

class Challenge {
  Challenge.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        tipo = j['tipo'] as String,
        descripcion = j['descripcion'] as String,
        objetivo = _num(j['objetivo']),
        valorActual = _num(j['valor_actual']),
        fechaFin = _date(j['fecha_fin']),
        estado = j['estado'] as String,
        puntos = j['puntos'] as int;

  final int id;
  final String tipo;
  final String descripcion;
  final double objetivo;
  final double valorActual;
  final DateTime fechaFin;
  final String estado;
  final int puntos;

  bool get activo => estado == 'activo';

  /// En "reducir" el objetivo es un tope (cuanto menos, mejor); en los demás
  /// es una cantidad a acumular.
  bool get esTope => tipo == 'reducir_categoria';

  double get progreso => objetivo <= 0 ? 0 : (valorActual / objetivo).clamp(0, 1).toDouble();
}

class ChallengeSuggestion {
  ChallengeSuggestion.fromJson(Map<String, dynamic> j)
      : plantilla = j['plantilla'] as String,
        categoryId = j['category_id'] as int?,
        porcentaje = j['porcentaje'] as int?,
        titulo = j['titulo'] as String,
        motivo = j['motivo'] as String,
        puntos = j['puntos'] as int;

  final String plantilla;
  final int? categoryId;
  final int? porcentaje;
  final String titulo;
  final String motivo;
  final int puntos;

  Map<String, dynamic> toPayload() => {
        'plantilla': plantilla,
        if (categoryId != null) 'category_id': categoryId,
        if (porcentaje != null) 'porcentaje': porcentaje,
      };
}

class BadgeInfo {
  BadgeInfo.fromJson(Map<String, dynamic> j)
      : codigo = j['codigo'] as String,
        nombre = j['nombre'] as String,
        descripcion = j['descripcion'] as String,
        desbloqueada = j['desbloqueada'] as bool;

  final String codigo;
  final String nombre;
  final String descripcion;
  final bool desbloqueada;
}

class PointEvent {
  PointEvent.fromJson(Map<String, dynamic> j)
      : tipo = j['tipo'] as String,
        puntos = j['puntos'] as int,
        fecha = _date(j['fecha']);

  final String tipo;
  final int puntos;
  final DateTime fecha;
}

class GamificationProfile {
  GamificationProfile.fromJson(Map<String, dynamic> j)
      : puntos = j['puntos'] as int,
        nivelNumero = j['nivel']['numero'] as int,
        nivelNombre = j['nivel']['nombre'] as String,
        puntosNivel = j['nivel']['puntos_nivel'] as int,
        puntosSiguiente = j['nivel']['puntos_siguiente'] as int?,
        rachaActual = j['racha_actual'] as int,
        mejorRacha = j['mejor_racha'] as int,
        ratioAhorro = _numOrNull(j['metricas']['ratio_ahorro']),
        consistencia = _num(j['metricas']['consistencia']),
        mejoraMensual = _numOrNull(j['metricas']['mejora_mensual']),
        insignias = _list(j['insignias'], BadgeInfo.fromJson),
        eventos = _list(j['eventos_recientes'], PointEvent.fromJson),
        nuevosPuntos = j['nuevos_puntos'] as int,
        nuevasInsignias = (j['nuevas_insignias'] as List).cast<String>();

  final int puntos;
  final int nivelNumero;
  final String nivelNombre;
  final int puntosNivel;
  final int? puntosSiguiente;
  final int rachaActual;
  final int mejorRacha;
  final double? ratioAhorro;
  final double consistencia;
  final double? mejoraMensual;
  final List<BadgeInfo> insignias;
  final List<PointEvent> eventos;
  final int nuevosPuntos;
  final List<String> nuevasInsignias;

  double get progresoNivel {
    final siguiente = puntosSiguiente;
    if (siguiente == null) return 1;
    return ((puntos - puntosNivel) / (siguiente - puntosNivel)).clamp(0, 1).toDouble();
  }
}

class CategoryAmount {
  CategoryAmount.fromJson(Map<String, dynamic> j)
      : categoria = j['categoria'] as String,
        monto = _num(j['monto']);

  final String categoria;
  final double monto;
}

class WeeklyReport {
  WeeklyReport.fromJson(Map<String, dynamic> j)
      : semanaInicio = _date(j['semana_inicio']),
        semanaFin = _date(j['semana_fin']),
        gastoTotal = _num(j['gasto_total_semana']),
        porCategoria = _list(j['gasto_por_categoria'], CategoryAmount.fromJson),
        ritmoEsperado = _num(j['ritmo_esperado_semanal']),
        diferencia = _num(j['diferencia_vs_ritmo']),
        recomendaciones = j['recomendaciones'] as String;

  final DateTime semanaInicio;
  final DateTime semanaFin;
  final double gastoTotal;
  final List<CategoryAmount> porCategoria;
  final double ritmoEsperado;
  final double diferencia;
  final String recomendaciones;
}

class TrendWeek {
  TrendWeek.fromJson(Map<String, dynamic> j)
      : inicio = _date(j['semana_inicio']),
        fin = _date(j['semana_fin']),
        total = _num(j['total']),
        porCategoria = _list(j['por_categoria'], CategoryAmount.fromJson);

  final DateTime inicio;
  final DateTime fin;
  final double total;
  final List<CategoryAmount> porCategoria;
}

class TrendDay {
  TrendDay.fromJson(Map<String, dynamic> j)
      : fecha = _date(j['fecha']),
        total = _num(j['total']);

  final DateTime fecha;
  final double total;
}

/// Gasto por semana (de la más antigua a la actual) y día a día de las dos
/// últimas semanas, para las gráficas.
class Trends {
  Trends.fromJson(Map<String, dynamic> j)
      : semanas = _list(j['semanas'], TrendWeek.fromJson),
        dias = _list(j['dias'], TrendDay.fromJson),
        promedioSemanal = _num(j['promedio_semanal']),
        variacionPct = j['variacion_vs_semana_anterior_pct'] as int?;

  final List<TrendWeek> semanas;
  final List<TrendDay> dias;
  final double promedioSemanal;
  final int? variacionPct;

  TrendWeek get semanaActual => semanas.last;
  bool get sinGastos => semanas.every((s) => s.total <= 0);
}

class Wrapped {
  Wrapped.fromJson(Map<String, dynamic> j)
      : anio = j['anio'] as int,
        mes = j['mes'] as int,
        gastoTotal = _num(j['gasto_total']),
        numGastos = j['num_gastos'] as int,
        diasConRegistro = j['dias_con_registro'] as int,
        categoriaTop = j['categoria_top']?['categoria'] as String?,
        categoriaTopPct = j['categoria_top']?['porcentaje'] as int?,
        gastoMayor = j['gasto_mayor']?['descripcion'] as String?,
        gastoMayorMonto = _numOrNull(j['gasto_mayor']?['monto']),
        variacionPct = j['variacion_vs_mes_anterior_pct'] as int?,
        aportadoAMetas = _num(j['aportado_a_metas']),
        puntosGanados = j['puntos_ganados'] as int,
        insignias = (j['insignias'] as List).cast<String>(),
        animoFrecuente = j['animo_frecuente'] as String?,
        fraseCoach = j['frase_coach'] as String;

  final int anio;
  final int mes;
  final double gastoTotal;
  final int numGastos;
  final int diasConRegistro;
  final String? categoriaTop;
  final int? categoriaTopPct;
  final String? gastoMayor;
  final double? gastoMayorMonto;
  final int? variacionPct;
  final double aportadoAMetas;
  final int puntosGanados;
  final List<String> insignias;
  final String? animoFrecuente;
  final String fraseCoach;
}
