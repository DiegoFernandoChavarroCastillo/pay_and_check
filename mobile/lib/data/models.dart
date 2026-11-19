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
        zonaHoraria = j['zona_horaria'] as String,
        politicaVigente = j['politica_vigente'] as bool? ?? false,
        aceptoPoliticaAntes = j['politica_version'] != null,
        smsConsentido = j['sms_consent_at'] != null;

  final int id;
  final String email;
  final String nombre;
  final String coachTone;
  final String idioma;
  final String zonaHoraria;

  /// Aceptó la versión vigente de la política. Si es false la app solo deja
  /// ver la pantalla de consentimiento.
  final bool politicaVigente;

  /// Aceptó alguna versión: distingue "la política cambió" de "nunca la aceptó".
  final bool aceptoPoliticaAntes;

  /// Dio el permiso aparte para leer los SMS del banco.
  final bool smsConsentido;
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

/// Gasto fijo (arriendo, recibos, transporte) que vence cada semana o cada mes.
/// No se registra solo: el día que toca queda por pagar hasta que se confirma.
class RecurringExpense {
  RecurringExpense.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        categoryId = j['category_id'] as int,
        monto = _num(j['monto']),
        descripcion = j['descripcion'] as String,
        mensual = j['frecuencia'] == 'mensual',
        diaSemana = j['dia_semana'] as int? ?? 0,
        diaMes = j['dia_mes'] as int?,
        activo = j['activo'] as bool,
        proximoVencimiento = _dateOrNull(j['proximo_vencimiento']),
        pendienteDesde = _dateOrNull(j['pendiente_desde']);

  final int id;
  final int categoryId;
  final double monto;
  final String descripcion;
  final bool mensual;

  /// 0 = lunes … 6 = domingo. Solo aplica si es semanal.
  final int diaSemana;

  /// 1 a 31; en meses más cortos vence el último día. Solo aplica si es mensual.
  final int? diaMes;
  final bool activo;
  final DateTime? proximoVencimiento;

  /// Vencimiento que espera confirmación, si lo hay.
  final DateTime? pendienteDesde;

  /// Las próximas [n] fechas de vencimiento a partir de [desde] (ese día incluido).
  /// Sirve para programar los recordatorios en el teléfono.
  List<DateTime> proximosVencimientos(DateTime desde, int n) {
    final hoy = DateTime(desde.year, desde.month, desde.day);
    final fechas = <DateTime>[];
    if (mensual) {
      final dia = diaMes ?? 1;
      for (var m = 0; fechas.length < n; m++) {
        // El día 0 del mes siguiente es el último de este: así el 31 cae en 28, 29 o 30.
        final ultimo = DateTime(hoy.year, hoy.month + m + 1, 0).day;
        final vence = DateTime(hoy.year, hoy.month + m, dia > ultimo ? ultimo : dia);
        if (!vence.isBefore(hoy)) fechas.add(vence);
      }
    } else {
      final primero = hoy.add(Duration(days: (diaSemana - (hoy.weekday - 1)) % 7));
      for (var i = 0; i < n; i++) {
        fechas.add(DateTime(primero.year, primero.month, primero.day + 7 * i));
      }
    }
    return fechas;
  }
}

/// Un gasto fijo que ya venció y espera que la persona confirme que lo pagó.
class PendingPayment {
  PendingPayment.fromJson(Map<String, dynamic> j)
      : recurringId = j['recurring_id'] as int,
        categoryId = j['category_id'] as int,
        descripcion = j['descripcion'] as String,
        monto = _num(j['monto']),
        fecha = _date(j['fecha']);

  final int recurringId;
  final int categoryId;
  final String descripcion;
  final double monto;
  final DateTime fecha;
}

/// Borrador de un movimiento: lo que devuelve la IA al parsear un texto o un recibo,
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
    this.esIngreso = false,
    this.adicionales = const [],
  });

  ExpenseDraft.fromParse(Map<String, dynamic> j, {required this.source, this.textoOriginal})
      : esIngreso = j['tipo'] == 'ingreso',
        monto = _num(j['monto']),
        categoria = j['categoria'] as String?,
        descripcion = j['descripcion'] as String?,
        fecha = _dateOrNull(j['fecha']),
        comercio = j['comercio'] as String?,
        adicionales = [
          for (final a in (j['adicionales'] as List?) ?? const [])
            ExpenseDraft.fromParse(a as Map<String, dynamic>, source: source, textoOriginal: textoOriginal),
        ];

  final double? monto;
  final String? categoria;
  final String? descripcion;
  final DateTime? fecha;
  final String? comercio;
  final String source;
  final String? textoOriginal;

  /// El texto hablaba de dinero recibido ("me pagaron…"): se confirma como ingreso, sin categoría.
  final bool esIngreso;

  /// Los demás movimientos de la misma frase ("almuerzo 18 mil y un uber de 12.500"): se confirman uno tras otro.
  final List<ExpenseDraft> adicionales;
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
        contenido = j['contenido'] as String,
        accion = j['accion'] == null ? null : InsightAction.fromJson(j['accion'] as Map<String, dynamic>);

  ChatMessage.local(this.contenido)
      : id = -1,
        esDelCoach = false,
        accion = null;

  final int id;
  final bool esDelCoach;
  final String contenido;

  /// Acción de un toque bajo la respuesta ("Crear meta: Viaje", "Registrar este gasto"). Solo llega en la
  /// respuesta recién enviada; el historial no la guarda.
  final InsightAction? accion;
}

/// "¿Me alcanza?": cómo quedaría el presupuesto si hoy se gastara [monto]. No guarda nada. (No se llama
/// `Simulation` para no chocar con la clase de física de Flutter.)
class AffordCheck {
  AffordCheck.fromJson(Map<String, dynamic> j)
      : monto = _num(j['monto']),
        alcanza = j['alcanza'] as bool,
        porDiaAntes = _num(j['disponible_por_dia_antes']),
        porDiaDespues = _num(j['disponible_por_dia_despues']),
        totalDespues = _num(j['disponible_total_despues']),
        diasRestantes = j['dias_restantes'] as int,
        enRiesgo = j['en_riesgo_despues'] as bool,
        fechaAgotamiento = _dateOrNull(j['fecha_agotamiento_despues']),
        metaNombre = (j['meta'] as Map<String, dynamic>?)?['nombre'] as String?,
        metaDias = (j['meta'] as Map<String, dynamic>?)?['dias_equivalentes'] as int?;

  final double monto;
  final bool alcanza;
  final double porDiaAntes;
  final double porDiaDespues;
  final double totalDespues;
  final int diasRestantes;
  final bool enRiesgo;
  final DateTime? fechaAgotamiento;
  final String? metaNombre;

  /// A cuántos días del ahorro que pide la meta equivale la compra.
  final int? metaDias;
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
  /// Retos de "no pasarse de un monto": se muestran como gasto acumulado frente al tope.
  bool get esTope => tipo == 'reducir_categoria' || tipo == 'semana_en_ritmo';

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
        diasActivos = (j['metricas']['dias_activos'] as int?) ?? 0,
        diasVentana = (j['metricas']['dias_ventana'] as int?) ?? 0,
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
  final int diasActivos;
  final int diasVentana;
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

/// Un plan del catálogo (`GET /plans`). Precio en pesos con IVA.
class Plan {
  Plan.fromJson(Map<String, dynamic> j)
      : codigo = j['codigo'] as String,
        precio = j['precio_cop'] as int,
        cupoIa = j['cupo_ia_mensual'] as int,
        compartido = j['compartido'] as bool,
        estadoDemo = j['estado_demo'] as String,
        maxIntegrantes = j['max_integrantes'] as int?,
        funciones = ((j['funciones'] as List?) ?? const []).cast<String>();

  final String codigo;
  final int precio;
  final int cupoIa;
  final bool compartido;

  /// "real" o "simulado" (Premium y Familiar no cobran en el piloto).
  final String estadoDemo;
  final int? maxIntegrantes;

  /// Lo que incluye el plan ("simulador", "captura_automatica"…): se muestra como lista de beneficios.
  final List<String> funciones;
}

class Family {
  Family.fromJson(Map<String, dynamic> j)
      : codigo = j['codigo'] as String,
        integrantes = j['integrantes'] as int,
        maxIntegrantes = j['max_integrantes'] as int,
        esTitular = j['es_titular'] as bool,
        comparteProgreso = (j['comparte_progreso'] as bool?) ?? false;

  final String codigo;
  final int integrantes;
  final int maxIntegrantes;
  final bool esTitular;

  /// Si deja que el titular vea su progreso agregado (constancia, metas, si el presupuesto alcanza).
  final bool comparteProgreso;
}

/// El plan de la persona y cuánto le queda de su cupo de IA este mes (`GET /me/subscription`).
class Subscription {
  Subscription.fromJson(Map<String, dynamic> j)
      : plan = j['plan'] as String,
        cupoIa = j['cupo_ia_mensual'] as int,
        usadas = j['usadas'] as int,
        restantes = j['restantes'] as int,
        compartido = j['compartido'] as bool,
        reiniciaEl = _date(j['reinicia_el']),
        organizacion = j['organizacion'] as String?,
        familia = j['familia'] == null ? null : Family.fromJson(j['familia'] as Map<String, dynamic>),
        aviso = j['aviso'] as String?;

  final String plan;
  final int cupoIa;
  final int usadas;
  final int restantes;
  final bool compartido;
  final DateTime reiniciaEl;
  final String? organizacion;
  final Family? familia;

  /// Aviso del backend para los planes simulados ("no hay cobro real").
  final String? aviso;
}

// --- Funciones añadidas tras el análisis de competidores (noviembre 2026) ---

/// Un apoyo de la universidad del convenio (beca, auxilio de alimentación, apoyo psicológico…).
class SupportResource {
  SupportResource.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        tipo = j['tipo'] as String,
        titulo = j['titulo'] as String,
        descripcion = j['descripcion'] as String,
        contacto = j['contacto'] as String,
        meInteresa = j['me_interesa'] as bool;

  final int id;
  final String tipo;
  final String titulo;
  final String descripcion;
  final String contacto;
  final bool meInteresa;
}

class SupportList {
  SupportList.fromJson(Map<String, dynamic> j)
      : organizacion = j['organizacion'] as String?,
        motivo = j['motivo_sugerencia'] as String?,
        apoyos = _list(j['apoyos'], SupportResource.fromJson);

  final String? organizacion;

  /// "en_riesgo" o "estres": por qué la app los sugiere ahora. Null si no hay motivo.
  final String? motivo;
  final List<SupportResource> apoyos;
}

/// Un gasto grande que viene (matrícula, libros, regalos…).
class PlannedExpense {
  PlannedExpense.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        descripcion = j['descripcion'] as String,
        monto = _num(j['monto']),
        fecha = _date(j['fecha']),
        dias = j['dias'] as int?,
        porSemana = _numOrNull(j['por_semana']),
        margenSemanal = _numOrNull(j['margen_semanal']);

  final int id;
  final String descripcion;
  final double monto;
  final DateTime fecha;
  final int? dias;
  final double? porSemana;

  /// Lo que se puede gastar por semana menos lo que hay que apartar; negativo = al ritmo de hoy no alcanza.
  final double? margenSemanal;
}

/// Lo que alguien le debe a la persona por una vaca.
class Receivable {
  Receivable.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        persona = j['persona'] as String,
        descripcion = j['descripcion'] as String,
        monto = _num(j['monto']),
        fecha = _date(j['fecha']);

  final int id;
  final String persona;
  final String descripcion;
  final double monto;
  final DateTime fecha;
}

class ReceivableSummary {
  ReceivableSummary.fromJson(Map<String, dynamic> j)
      : total = _num(j['total_pendiente']),
        pendientes = _list(j['pendientes'], Receivable.fromJson);

  final double total;
  final List<Receivable> pendientes;
}

/// Un gasto hormiga o una suscripción.
class RepeatedSpend {
  RepeatedSpend.fromJson(Map<String, dynamic> j)
      : nombre = j['nombre'] as String,
        tipo = j['tipo'] as String,
        veces = j['veces'] as int,
        porMes = _num(j['por_mes']),
        porSemestre = _num(j['por_semestre']);

  final String nombre;
  final String tipo;
  final int veces;
  final double porMes;
  final double porSemestre;
}

/// "¿Me conviene este crédito?".
class CreditCheck {
  CreditCheck.fromJson(Map<String, dynamic> j)
      : cuota = _num(j['cuota']),
        cuotas = j['cuotas'] as int,
        tasaMensual = _num(j['tasa_mensual']),
        totalPagado = _num(j['total_pagado']),
        intereses = _num(j['intereses']),
        porDia = _num(j['por_dia']),
        porDiaHoy = _numOrNull(j['disponible_por_dia']),
        porDiaConCuota = _numOrNull(j['disponible_por_dia_con_cuota']);

  final double cuota;
  final int cuotas;
  final double tasaMensual;
  final double totalPagado;
  final double intereses;
  final double porDia;
  final double? porDiaHoy;
  final double? porDiaConCuota;
}

/// Lo que el titular del plan Familiar ve de un integrante (solo si lo comparte).
class FamilyMemberProgress {
  FamilyMemberProgress.fromJson(Map<String, dynamic> j)
      : nombre = j['nombre'] as String,
        comparte = j['comparte'] as bool,
        racha = j['racha'] as int?,
        constancia = _numOrNull(j['constancia']),
        metasActivas = j['metas_activas'] as int?,
        progresoMetas = _numOrNull(j['progreso_metas']),
        presupuestoAlcanza = j['presupuesto_alcanza'] as bool?;

  final String nombre;
  final bool comparte;
  final int? racha;
  final double? constancia;
  final int? metasActivas;
  final double? progresoMetas;
  final bool? presupuestoAlcanza;
}
