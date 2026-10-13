"""Resumen mensual tipo "Wrapped": lo más destacado del mes, calculado solo
con datos reales. La IA aporta, si está disponible, una frase de cierre."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.category import Category
from app.models.coach import EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Achievement, PointEvent
from app.models.goal import GoalContribution
from app.models.income import Income
from app.models.user import User
from app.services.budget_totals import gasto_entre, ratio_ahorro
from app.services.coach import reglas_para, rompe_guardrails
from app.services.gamification import insignia_texto
from app.services.groq_client import GroqServiceError, generate_coach_text
from app.services.patterns import fmt
from app.services.prompts import build_coach_wrapped_prompt

_CIERRE = {
    "es": "Registraste {n} gastos en {dias} días este mes. Cada registro es una decisión más consciente.",
    "en": "You logged {n} expenses across {dias} days this month. Every entry is a more mindful decision.",
}


def rango_del_mes(anio: int, mes: int) -> tuple[date, date]:
    inicio = date(anio, mes, 1)
    siguiente = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return inicio, siguiente - timedelta(days=1)


def _suma(session: Session, columna, *condiciones) -> Decimal:
    return Decimal(session.exec(select(func.coalesce(func.sum(columna), 0)).where(*condiciones)).one())


def build_wrapped(session: Session, user: User, anio: int, mes: int) -> dict:
    inicio, fin = rango_del_mes(anio, mes)
    gastos = session.exec(
        select(Expense, Category.nombre)
        .join(Category, Category.id == Expense.category_id)
        .where(Expense.user_id == user.id)
        .where(Expense.fecha >= inicio)
        .where(Expense.fecha <= fin)
    ).all()

    gasto_total = sum((g.monto for g, _ in gastos), Decimal("0"))
    por_categoria: dict[str, Decimal] = defaultdict(Decimal)
    por_dia: dict[date, Decimal] = defaultdict(Decimal)
    for gasto, categoria in gastos:
        por_categoria[categoria] += gasto.monto
        por_dia[gasto.fecha] += gasto.monto

    categoria_top = None
    if por_categoria:
        nombre, monto = max(por_categoria.items(), key=lambda item: item[1])
        categoria_top = {"categoria": nombre, "monto": monto, "porcentaje": int(monto / gasto_total * 100)}

    gasto_mayor = None
    if gastos:
        mayor, categoria = max(gastos, key=lambda fila: fila[0].monto)
        gasto_mayor = {
            "descripcion": mayor.descripcion,
            "monto": mayor.monto,
            "fecha": mayor.fecha,
            "categoria": categoria,
        }

    dia_mas_gasto = None
    if por_dia:
        dia, monto = max(por_dia.items(), key=lambda item: item[1])
        dia_mas_gasto = {"fecha": dia, "monto": monto}

    inicio_previo, fin_previo = rango_del_mes(*((anio - 1, 12) if mes == 1 else (anio, mes - 1)))
    gasto_previo = gasto_entre(session, user.id, inicio_previo, fin_previo)
    variacion = int((gasto_total / gasto_previo - 1) * 100) if gasto_previo > 0 else None

    animos = Counter(
        session.exec(
            select(EmotionalCheckin.animo)
            .where(EmotionalCheckin.user_id == user.id)
            .where(EmotionalCheckin.fecha >= inicio)
            .where(EmotionalCheckin.fecha <= fin)
        ).all()
    )
    insignias = session.exec(
        select(Achievement.codigo)
        .where(Achievement.user_id == user.id)
        .where(func.date(Achievement.unlocked_at) >= inicio)
        .where(func.date(Achievement.unlocked_at) <= fin)
    ).all()

    wrapped = {
        "anio": anio,
        "mes": mes,
        "gasto_total": gasto_total,
        "ingresos_total": _suma(
            session, Income.monto, Income.user_id == user.id, Income.fecha >= inicio, Income.fecha <= fin
        ),
        "num_gastos": len(gastos),
        "dias_con_registro": len({g.fecha for g, _ in gastos if g.source != "recurrente"}),
        "categoria_top": categoria_top,
        "gasto_mayor": gasto_mayor,
        "dia_mas_gasto": dia_mas_gasto,
        "variacion_vs_mes_anterior_pct": variacion,
        "ratio_ahorro": ratio_ahorro(session, user.id, inicio, fin),
        "aportado_a_metas": _suma(
            session,
            GoalContribution.monto,
            GoalContribution.user_id == user.id,
            GoalContribution.fecha >= inicio,
            GoalContribution.fecha <= fin,
        ),
        "puntos_ganados": int(
            _suma(
                session,
                PointEvent.puntos,
                PointEvent.user_id == user.id,
                PointEvent.fecha >= inicio,
                PointEvent.fecha <= fin,
            )
        ),
        "insignias": [insignia_texto(codigo, user.idioma)[0] for codigo in insignias],
        "animo_frecuente": animos.most_common(1)[0][0] if animos else None,
    }
    wrapped["frase_coach"] = _frase_de_cierre(user, wrapped)
    return wrapped


def _frase_de_cierre(user: User, wrapped: dict) -> str:
    respaldo = _CIERRE.get(user.idioma, _CIERRE["es"]).format(
        n=wrapped["num_gastos"], dias=wrapped["dias_con_registro"]
    )
    if wrapped["num_gastos"] == 0:
        return respaldo

    lineas = [
        f"Gasto total del mes: {fmt(wrapped['gasto_total'])} en {wrapped['num_gastos']} gastos.",
        f"Días con registro: {wrapped['dias_con_registro']}.",
        f"Puntos ganados: {wrapped['puntos_ganados']}. Apartado a metas: {fmt(wrapped['aportado_a_metas'])}.",
    ]
    if wrapped["categoria_top"]:
        top = wrapped["categoria_top"]
        lineas.append(f"Categoría principal: {top['categoria']} ({top['porcentaje']}% del gasto).")
    if wrapped["variacion_vs_mes_anterior_pct"] is not None:
        lineas.append(f"Variación frente al mes anterior: {wrapped['variacion_vs_mes_anterior_pct']}%.")

    try:
        frase = generate_coach_text(build_coach_wrapped_prompt(reglas_para(user), "\n".join(lineas)))
    except GroqServiceError:
        return respaldo
    return respaldo if not frase or rompe_guardrails(frase) else frase
