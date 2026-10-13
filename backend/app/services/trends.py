from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.category import Category
from app.models.expense import Expense
from app.services.weekly_report import CategoriaGasto, _redondear

CERO = Decimal("0.00")


@dataclass
class SemanaTendencia:
    semana_inicio: date
    semana_fin: date
    total: Decimal
    por_categoria: list[CategoriaGasto] = field(default_factory=list)


@dataclass
class DiaTendencia:
    fecha: date
    total: Decimal


@dataclass
class Trends:
    semanas: list[SemanaTendencia]
    dias: list[DiaTendencia]
    promedio_semanal: Decimal
    variacion_vs_semana_anterior_pct: int | None


def _promedio(semanas: list[SemanaTendencia]) -> Decimal:
    """Promedio desde la primera semana con gasto: las semanas vacías de antes de que la persona
    empezara a registrar no son semanas "de cero" y bajarían el promedio."""
    desde = next((i for i, s in enumerate(semanas) if s.total > 0), None)
    if desde is None:
        return CERO
    activas = semanas[desde:]
    return _redondear(sum((s.total for s in activas), CERO) / len(activas))


def build_trends(session: Session, user_id: int, today: date, semanas: int = 8) -> Trends:
    """Gasto de las últimas `semanas` semanas calendario (lunes a domingo), la
    última es la que contiene `today`. Solo agrega, sin IA.

    Filtra por usuario y fechas, no por presupuesto: la tendencia no debe
    cortarse cuando un periodo termina y empieza otro. Las semanas y los días
    sin gasto salen en 0 para que la gráfica no tenga huecos.
    """
    inicio_actual = today - timedelta(days=today.weekday())
    desde = inicio_actual - timedelta(weeks=semanas - 1)
    hasta = inicio_actual + timedelta(days=6)

    rows = session.exec(
        select(Expense.fecha, Category.nombre, func.coalesce(func.sum(Expense.monto), 0))
        .join(Category, Expense.category_id == Category.id)
        .where(Expense.user_id == user_id)
        .where(Expense.fecha >= desde)
        .where(Expense.fecha <= hasta)
        .group_by(Expense.fecha, Category.nombre)
    ).all()

    por_dia: dict[date, Decimal] = defaultdict(lambda: CERO)
    por_semana: dict[date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    for fecha, categoria, monto in rows:
        monto = Decimal(monto)
        por_dia[fecha] += monto
        por_semana[fecha - timedelta(days=fecha.weekday())][categoria] += monto

    resultado = []
    for i in range(semanas):
        inicio = desde + timedelta(weeks=i)
        categorias = sorted(
            (CategoriaGasto(categoria=nombre, monto=_redondear(monto)) for nombre, monto in por_semana[inicio].items()),
            key=lambda c: c.monto,
            reverse=True,
        )
        resultado.append(
            SemanaTendencia(
                semana_inicio=inicio,
                semana_fin=inicio + timedelta(days=6),
                total=_redondear(sum((c.monto for c in categorias), CERO)),
                por_categoria=categorias,
            )
        )

    # Dos semanas completas día a día: la anterior y la actual.
    inicio_dias = inicio_actual - timedelta(weeks=1)
    dias = [
        DiaTendencia(fecha=dia, total=_redondear(por_dia[dia]))
        for dia in (inicio_dias + timedelta(days=n) for n in range(14))
    ]

    actual, anterior = resultado[-1].total, resultado[-2].total
    variacion = None if anterior <= 0 else int(round((actual - anterior) / anterior * 100))

    return Trends(
        semanas=resultado,
        dias=dias,
        promedio_semanal=_promedio(resultado),
        variacion_vs_semana_anterior_pct=variacion,
    )
