"""Gastos hormiga y suscripciones: pagos que se repiten y que, sumados, pesan. Determinista: se agrupan los
gastos de los últimos 90 días por comercio o descripción normalizada.

- Hormiga: montos pequeños (≤ `MAX_HORMIGA`) de categorías opcionales que se repiten al menos
  `MIN_VECES_HORMIGA` veces (el bus o las fotocopias no son hormiga: son gastos fijos).
- Suscripción: un mismo concepto en al menos 2 meses distintos, con montos parecidos (±15 %), salvo vivienda,
  deudas y estudio (el arriendo no es una suscripción)."""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.models.category import Category
from app.models.expense import Expense
from app.services.ia_seguridad import sin_tildes

VENTANA_DIAS = 90
# "Hormiga" es lo pequeño y opcional que se repite (el tinto, el snack), no el almuerzo ni el bus.
MAX_HORMIGA = Decimal("12000")
# Lo que nunca es una "suscripción" aunque se repita cada mes.
# Los servicios (celular, internet, luz) son básicos: repetirse cada mes no los vuelve recortables.
NO_SUSCRIPCION = ("vivienda", "deudas", "estudio", "servicios")
MIN_VECES_HORMIGA = 4
TOLERANCIA_SUSCRIPCION = Decimal("0.15")
# Un semestre universitario dura unos 4,5 meses: se usa para "esto te cuesta al semestre".
MESES_SEMESTRE = Decimal("4.5")

_RUIDO = re.compile(r"\b(compra|pago|en|de|la|el|del|por|a|un|una|cop|\d+)\b")


def clave_de(texto: str) -> str:
    """ "Domicilio de Rappi" y "domicilio rappi 32000" son el mismo concepto."""
    plano = sin_tildes(texto.lower())
    plano = re.sub(r"[^a-zñ0-9 ]", " ", plano)
    plano = _RUIDO.sub(" ", plano)
    return " ".join(plano.split())[:40]


@dataclass
class Repetido:
    nombre: str
    tipo: str  # "hormiga" | "suscripcion"
    veces: int
    total: Decimal  # en la ventana
    por_mes: Decimal
    por_semestre: Decimal


def detectar(session: Session, user_id: int, today: date) -> list[Repetido]:
    desde = today - timedelta(days=VENTANA_DIAS - 1)
    gastos = session.exec(
        select(Expense).where(Expense.user_id == user_id, Expense.fecha >= desde, Expense.fecha <= today)
    ).all()
    categorias = {c.id: c for c in session.exec(select(Category)).all()}
    grupos: dict[str, list[Expense]] = defaultdict(list)
    nombres: dict[str, str] = {}
    for g in gastos:
        clave = clave_de(g.comercio or g.descripcion)
        if not clave:
            continue
        grupos[clave].append(g)
        nombres.setdefault(clave, (g.comercio or g.descripcion).strip())

    meses_ventana = Decimal(VENTANA_DIAS) / Decimal(30)
    resultado = []
    for clave, lista in grupos.items():
        montos = [g.monto for g in lista]
        total = sum(montos, Decimal("0"))
        meses = {(g.fecha.year, g.fecha.month) for g in lista}
        promedio = total / len(montos)
        parecidos = all(abs(m - promedio) <= promedio * TOLERANCIA_SUSCRIPCION for m in montos)
        categoria = categorias.get(lista[0].category_id)
        nombre_cat = categoria.nombre if categoria else ""
        opcional = categoria is not None and categoria.tipo == "opcional"
        if len(meses) >= 2 and len(lista) <= len(meses) + 1 and parecidos and nombre_cat not in NO_SUSCRIPCION:
            tipo, por_mes = "suscripcion", promedio
        elif len(lista) >= MIN_VECES_HORMIGA and promedio <= MAX_HORMIGA and opcional:
            tipo, por_mes = "hormiga", total / meses_ventana
        else:
            continue
        por_mes = por_mes.quantize(Decimal("1"))
        resultado.append(
            Repetido(nombres[clave], tipo, len(lista), total.quantize(Decimal("1")), por_mes,
                     (por_mes * MESES_SEMESTRE).quantize(Decimal("1")))
        )
    return sorted(resultado, key=lambda r: -r.por_mes)
