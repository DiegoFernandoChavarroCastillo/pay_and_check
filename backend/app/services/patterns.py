"""Detección de patrones de gasto. Todo aquí es determinista y se calcula con
los datos reales del usuario: la IA solo redacta sobre estas cifras, nunca las
calcula ni las inventa."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, or_, select

from app.core.time import fmt_fecha
from app.models.category import Category
from app.models.coach import ANIMOS_BAJOS, EmotionalCheckin
from app.models.expense import Expense
from app.models.goal import Goal
from app.models.user import User
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for
from app.services.category_lookup import limite_de, limites_propios
from app.services.weekly_report import build_weekly_summary

VENTANA_DIAS = 28
# Umbrales a partir de los cuales una diferencia se considera un patrón.
FACTOR_FIN_DE_SEMANA = Decimal("1.3")
MIN_DIAS_FIN_DE_SEMANA = 2
AUMENTO_SEMANAL_MINIMO = Decimal("0.2")
PARTICIPACION_DOMINANTE = Decimal("0.4")
FACTOR_ANIMO = Decimal("1.2")

_TEXTOS = {
    "es": {
        "fin_de_semana": "En las últimas 4 semanas gastas en {categoria} un promedio de {fin} por día los fines "
        "de semana, frente a {semana} entre semana.",
        "variacion_semanal": "Esta semana llevas {actual} en {categoria}, {pct}% más que en los mismos días de "
        "la semana pasada ({anterior}).",
        "categoria_dominante": "{categoria} concentra el {pct}% de tu gasto de los últimos 30 días ({monto}).",
        "animo_gasto": "Los días que te sientes con ansiedad o preocupación gastas en promedio {bajo}, frente a "
        "{otro} los demás días.",
        "buen_ritmo": "Esta semana llevas {gasto}, por debajo de tu ritmo semanal de {ritmo}: tienes {margen} "
        "de margen.",
        "en_riesgo": "Al ritmo actual, tu presupuesto alcanzaría hasta el {fecha}, antes de que termine el "
        "periodo ({fin}).",
        "accion_reto": "Aceptar reto: {pct}% menos en {categoria}",
        "accion_limite": "Poner límite de {monto} a {categoria}",
        "accion_apartar": "Apartar {monto} para {meta}",
        "accion_meta": "Crear una meta de ahorro",
        "accion_checkins": "Aceptar reto: 5 check-ins esta semana",
        "accion_sin_gasto": "Aceptar reto: 3 días sin gasto opcional",
    },
    "en": {
        "fin_de_semana": "Over the last 4 weeks you spend an average of {fin} per day on {categoria} on "
        "weekends, versus {semana} on weekdays.",
        "variacion_semanal": "This week you have spent {actual} on {categoria}, {pct}% more than on the same "
        "days last week ({anterior}).",
        "categoria_dominante": "{categoria} makes up {pct}% of your spending over the last 30 days ({monto}).",
        "animo_gasto": "On days you feel anxious or worried you spend {bajo} on average, versus {otro} on "
        "other days.",
        "buen_ritmo": "This week you have spent {gasto}, below your weekly pace of {ritmo}: you have {margen} "
        "to spare.",
        "en_riesgo": "At the current pace your budget would last until {fecha}, before the period ends ({fin}).",
        "accion_reto": "Accept challenge: {pct}% less on {categoria}",
        "accion_limite": "Set a {monto} limit on {categoria}",
        "accion_apartar": "Set aside {monto} for {meta}",
        "accion_meta": "Create a savings goal",
        "accion_checkins": "Accept challenge: 5 check-ins this week",
        "accion_sin_gasto": "Accept challenge: 3 days without optional spending",
    },
}


@dataclass
class Pattern:
    tipo: str
    descripcion: str
    datos: dict = field(default_factory=dict)
    # Acción de un tap que la app puede ejecutar: {"tipo", "etiqueta", "payload"}.
    accion: dict | None = None


def fmt(valor: Decimal) -> str:
    """Monto sin decimales y con punto de miles, sin símbolo de moneda."""
    return f"{int(valor.to_integral_value()):,}".replace(",", ".")


def _t(idioma: str, clave: str, **kwargs) -> str:
    return _TEXTOS.get(idioma, _TEXTOS["es"])[clave].format(**kwargs)


def _gasto_por_dia_y_categoria(
    session: Session, user_id: int, desde: date, hasta: date
) -> dict[tuple[date, int], Decimal]:
    rows = session.exec(
        select(Expense.fecha, Expense.category_id, func.sum(Expense.monto))
        .where(Expense.user_id == user_id)
        .where(Expense.fecha >= desde)
        .where(Expense.fecha <= hasta)
        .group_by(Expense.fecha, Expense.category_id)
    ).all()
    return {(fecha, category_id): Decimal(monto) for fecha, category_id, monto in rows}


def _accion_reto(idioma: str, categoria: Category, porcentaje: int) -> dict:
    return {
        "tipo": "crear_reto",
        "etiqueta": _t(idioma, "accion_reto", pct=porcentaje, categoria=categoria.nombre),
        "payload": {"plantilla": "reducir_categoria", "category_id": categoria.id, "porcentaje": porcentaje},
    }


def _fin_de_semana(idioma, gastos, categorias, desde: date, hasta: date) -> Pattern | None:
    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    n_fin = sum(1 for d in dias if d.weekday() >= 5)
    n_semana = len(dias) - n_fin
    if not n_fin or not n_semana:
        return None

    total_fin: dict[int, Decimal] = defaultdict(Decimal)
    total_semana: dict[int, Decimal] = defaultdict(Decimal)
    dias_fin_con_gasto: dict[int, int] = defaultdict(int)
    for (fecha, category_id), monto in gastos.items():
        if fecha.weekday() >= 5:
            total_fin[category_id] += monto
            dias_fin_con_gasto[category_id] += 1
        else:
            total_semana[category_id] += monto

    mejor = None
    for category_id, total in total_fin.items():
        # Un solo día de fin de semana con gasto es una anécdota, no un patrón.
        if dias_fin_con_gasto[category_id] < MIN_DIAS_FIN_DE_SEMANA:
            continue
        prom_fin = total / n_fin
        prom_semana = total_semana.get(category_id, Decimal("0")) / n_semana
        if prom_fin >= prom_semana * FACTOR_FIN_DE_SEMANA and prom_fin > prom_semana:
            brecha = prom_fin - prom_semana
            if mejor is None or brecha > mejor[0]:
                mejor = (brecha, category_id, prom_fin, prom_semana)
    if mejor is None:
        return None

    _, category_id, prom_fin, prom_semana = mejor
    categoria = categorias[category_id]
    return Pattern(
        tipo="fin_de_semana",
        descripcion=_t(
            idioma, "fin_de_semana", categoria=categoria.nombre, fin=fmt(prom_fin), semana=fmt(prom_semana)
        ),
        datos={
            "category_id": category_id,
            "categoria": categoria.nombre,
            "promedio_fin_de_semana": str(prom_fin.quantize(Decimal("0.01"))),
            "promedio_entre_semana": str(prom_semana.quantize(Decimal("0.01"))),
        },
        accion=_accion_reto(idioma, categoria, 20),
    )


def _variacion_semanal(idioma, gastos, categorias, today: date) -> Pattern | None:
    lunes = today - timedelta(days=today.weekday())
    actual: dict[int, Decimal] = defaultdict(Decimal)
    anterior: dict[int, Decimal] = defaultdict(Decimal)
    for (fecha, category_id), monto in gastos.items():
        if lunes <= fecha <= today:
            actual[category_id] += monto
        elif lunes - timedelta(days=7) <= fecha <= today - timedelta(days=7):
            anterior[category_id] += monto

    mejor = None
    for category_id, monto in actual.items():
        previo = anterior.get(category_id, Decimal("0"))
        if previo > 0 and monto >= previo * (1 + AUMENTO_SEMANAL_MINIMO):
            if mejor is None or monto - previo > mejor[0]:
                mejor = (monto - previo, category_id, monto, previo)
    if mejor is None:
        return None

    _, category_id, monto, previo = mejor
    categoria = categorias[category_id]
    pct = int(((monto / previo) - 1) * 100)
    return Pattern(
        tipo="variacion_semanal",
        descripcion=_t(
            idioma, "variacion_semanal", categoria=categoria.nombre, actual=fmt(monto), anterior=fmt(previo), pct=pct
        ),
        datos={"category_id": category_id, "categoria": categoria.nombre, "aumento_pct": pct},
        accion=_accion_reto(idioma, categoria, 20),
    )


def _categoria_dominante(idioma, gastos, categorias, limites: dict, today: date) -> Pattern | None:
    desde = today - timedelta(days=29)
    totales: dict[int, Decimal] = defaultdict(Decimal)
    for (fecha, category_id), monto in gastos.items():
        if fecha >= desde:
            totales[category_id] += monto
    total = sum(totales.values(), Decimal("0"))
    # Con una sola categoría usada, "domina" por definición: no es un hallazgo.
    if total <= 0 or len(totales) < 2:
        return None

    category_id, monto = max(totales.items(), key=lambda item: item[1])
    if monto / total < PARTICIPACION_DOMINANTE:
        return None

    categoria = categorias[category_id]
    pct = int(monto / total * 100)
    # Se propone un límite si la persona aún no le ha puesto uno (propio o sobre una por defecto).
    if limite_de(categoria, limites) is None:
        limite = (monto * Decimal("0.9")).quantize(Decimal("1"))
        accion = {
            "tipo": "poner_limite",
            "etiqueta": _t(idioma, "accion_limite", monto=fmt(limite), categoria=categoria.nombre),
            "payload": {"category_id": category_id, "limite": str(limite)},
        }
    else:
        accion = _accion_reto(idioma, categoria, 10)

    return Pattern(
        tipo="categoria_dominante",
        descripcion=_t(idioma, "categoria_dominante", categoria=categoria.nombre, pct=pct, monto=fmt(monto)),
        datos={"category_id": category_id, "categoria": categoria.nombre, "participacion_pct": pct},
        accion=accion,
    )


def _animo_y_gasto(idioma, session: Session, gastos, user_id: int, today: date) -> Pattern | None:
    checkins = session.exec(
        select(EmotionalCheckin)
        .where(EmotionalCheckin.user_id == user_id)
        .where(EmotionalCheckin.fecha >= today - timedelta(days=29))
        .where(EmotionalCheckin.fecha <= today)
    ).all()

    gasto_del_dia: dict[date, Decimal] = defaultdict(Decimal)
    for (fecha, _), monto in gastos.items():
        gasto_del_dia[fecha] += monto

    bajos = [gasto_del_dia.get(c.fecha, Decimal("0")) for c in checkins if c.animo in ANIMOS_BAJOS]
    otros = [gasto_del_dia.get(c.fecha, Decimal("0")) for c in checkins if c.animo not in ANIMOS_BAJOS]
    if len(bajos) < 2 or len(otros) < 2:
        return None

    prom_bajo = sum(bajos, Decimal("0")) / len(bajos)
    prom_otro = sum(otros, Decimal("0")) / len(otros)
    if prom_bajo <= 0 or prom_bajo < prom_otro * FACTOR_ANIMO:
        return None

    return Pattern(
        tipo="animo_gasto",
        descripcion=_t(idioma, "animo_gasto", bajo=fmt(prom_bajo), otro=fmt(prom_otro)),
        datos={"dias_animo_bajo": len(bajos), "dias_otros": len(otros)},
        accion={
            "tipo": "crear_reto",
            "etiqueta": _t(idioma, "accion_checkins"),
            "payload": {"plantilla": "checkins"},
        },
    )


def _del_presupuesto(idioma, session: Session, user: User, today: date) -> list[Pattern]:
    budget = get_active_budget_for_user(session, user.id, today)
    if budget is None:
        return []

    summary = summary_for(session, budget, today)
    if summary.en_riesgo and summary.fecha_proyectada_agotamiento is not None:
        return [
            Pattern(
                tipo="en_riesgo",
                descripcion=_t(
                    idioma,
                    "en_riesgo",
                    fecha=fmt_fecha(summary.fecha_proyectada_agotamiento, idioma),
                    fin=fmt_fecha(budget.fecha_fin, idioma),
                ),
                datos={"fecha_proyectada_agotamiento": summary.fecha_proyectada_agotamiento.isoformat()},
                accion={
                    "tipo": "crear_reto",
                    "etiqueta": _t(idioma, "accion_sin_gasto"),
                    "payload": {"plantilla": "dias_sin_gasto"},
                },
            )
        ]

    semana = build_weekly_summary(session, user.id, budget, today)
    margen = -semana.diferencia_vs_ritmo
    if semana.gasto_total_semana <= 0 or margen <= 0:
        return []

    meta = session.exec(
        select(Goal).where(Goal.user_id == user.id).where(Goal.estado == "activa").order_by(Goal.created_at)
    ).first()
    # Se sugiere apartar la mitad del margen, sin pasarse de lo realmente disponible.
    sugerido = min(margen / 2, summary.disponible_total).quantize(Decimal("1"))
    # En miles cerrados cuando alcanza: nadie aparta "104.167".
    if sugerido >= 1000:
        sugerido = sugerido // 1000 * 1000
    if meta is not None and sugerido > 0:
        accion = {
            "tipo": "apartar_meta",
            "etiqueta": _t(idioma, "accion_apartar", monto=fmt(sugerido), meta=meta.nombre),
            "payload": {"goal_id": meta.id, "monto": str(sugerido)},
        }
    else:
        accion = {"tipo": "crear_meta", "etiqueta": _t(idioma, "accion_meta"), "payload": {}}

    return [
        Pattern(
            tipo="buen_ritmo",
            descripcion=_t(
                idioma,
                "buen_ritmo",
                gasto=fmt(semana.gasto_total_semana),
                ritmo=fmt(semana.ritmo_esperado_semanal),
                margen=fmt(margen),
            ),
            datos={"margen": str(margen)},
            accion=accion,
        )
    ]


def detect_patterns(session: Session, user: User, today: date) -> list[Pattern]:
    """Patrones vigentes del usuario, del más urgente al más general."""
    idioma = user.idioma
    desde = today - timedelta(days=VENTANA_DIAS - 1)
    # 30 días hacia atrás cubre todas las ventanas que usan los detectores.
    gastos = _gasto_por_dia_y_categoria(session, user.id, today - timedelta(days=29), today)
    categorias = {
        c.id: c
        for c in session.exec(
            select(Category).where(or_(Category.owner_id.is_(None), Category.owner_id == user.id))
        ).all()
    }
    gastos = {clave: monto for clave, monto in gastos.items() if clave[1] in categorias}

    candidatos = [
        *_del_presupuesto(idioma, session, user, today),
        _variacion_semanal(idioma, gastos, categorias, today),
        _fin_de_semana(
            idioma, {k: v for k, v in gastos.items() if k[0] >= desde}, categorias, desde, today
        ),
        _animo_y_gasto(idioma, session, gastos, user.id, today),
        _categoria_dominante(idioma, gastos, categorias, limites_propios(session, user.id), today),
    ]
    return [p for p in candidatos if p is not None]
