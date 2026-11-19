"""Simulaciones deterministas: "¿me alcanza si compro X?" y "¿cuánto aparto para juntar X antes de Y?".

Las usan el endpoint `POST /budgets/active/simulate` y el chat del coach. Ninguna cifra sale de la IA: el chat
recibe estas cuentas ya hechas y solo las redacta (la regla de siempre: la IA redacta, no calcula)."""

import calendar
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.models.budget import Budget
from app.services.budget_calculator import BudgetSummary, calculate_budget_summary
from app.services.ia_seguridad import sin_tildes

PESO = Decimal("1")


def _pesos(valor: Decimal) -> Decimal:
    return valor.quantize(PESO, rounding=ROUND_HALF_UP)


@dataclass
class PlanMeta:
    objetivo: Decimal
    ahorrado: Decimal
    falta: Decimal
    fecha_limite: date | None
    dias: int | None
    por_semana: Decimal | None
    por_dia: Decimal | None


def plan_de_meta(objetivo: Decimal, ahorrado: Decimal, fecha_limite: date | None, today: date) -> PlanMeta:
    """Cuánto hay que apartar por semana y por día para llegar a `objetivo` en `fecha_limite`. Sin fecha (o con
    una fecha ya pasada) no hay ritmo que calcular."""
    falta = max(objetivo - ahorrado, Decimal("0"))
    if fecha_limite is None or fecha_limite <= today:
        return PlanMeta(objetivo, ahorrado, falta, fecha_limite, None, None, None)
    dias = (fecha_limite - today).days
    semanas = Decimal(dias) / Decimal(7)
    por_semana = (falta / max(semanas, Decimal(1))).quantize(PESO, rounding=ROUND_CEILING)
    por_dia = (falta / dias).quantize(PESO, rounding=ROUND_CEILING)
    return PlanMeta(objetivo, ahorrado, falta, fecha_limite, dias, por_semana, por_dia)


@dataclass
class SimulacionCompra:
    monto: Decimal
    antes: BudgetSummary
    despues: BudgetSummary
    # Si hay una meta activa con fecha: a cuántos días de su ahorro diario equivale la compra.
    meta_nombre: str | None = None
    meta_dias_equivalentes: int | None = None

    @property
    def alcanza(self) -> bool:
        return self.despues.disponible_total >= 0

    @property
    def baja_por_dia(self) -> Decimal:
        return self.antes.disponible_por_dia - self.despues.disponible_por_dia


def simular_compra(
    budget: Budget,
    resumen: BudgetSummary,
    monto: Decimal,
    today: date,
    meta: PlanMeta | None = None,
    meta_nombre: str | None = None,
) -> SimulacionCompra:
    """El presupuesto como quedaría si hoy se gastara `monto`, sin guardar nada."""
    despues = calculate_budget_summary(
        budget,
        resumen.gastado_total + monto,
        resumen.ingresos_total,
        today=today,
        apartado_total=resumen.apartado_total,
    )
    sim = SimulacionCompra(monto=_pesos(monto), antes=resumen, despues=despues)
    if meta is not None and meta.por_dia and meta.por_dia > 0:
        sim.meta_nombre = meta_nombre
        sim.meta_dias_equivalentes = math.ceil(monto / meta.por_dia)
    return sim


# --- Lectura de montos y fechas en lenguaje natural (para el chat) -------------------------------------------

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

_MONTO = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)*)\s*(?P<escala>millones|millon|palos|palo|million|mil|k)?\b"
)


def _a_decimal(num: str, con_escala: bool) -> Decimal:
    if con_escala:
        # "2,5 millones" o "1.5 millones": aquí la coma o el punto son decimales.
        return Decimal(num.replace(",", "."))
    # "350.000", "1,000,000" o "350000": puntos y comas son separadores de miles.
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):
        return Decimal(re.sub(r"[.,]", "", num))
    return Decimal(num.replace(",", "."))


def monto_en(texto: str) -> Decimal | None:
    """El primer monto de dinero de un texto: "2 millones", "350 mil", "350.000", "$18000", "12k". Ignora
    números pequeños sin escala (un día del mes, "3 días")."""
    for m in _MONTO.finditer(sin_tildes(texto.lower())):
        escala = m.group("escala")
        try:
            valor = _a_decimal(m.group("num"), bool(escala))
        except ArithmeticError:
            continue
        if escala in ("millones", "millon", "palos", "palo", "million"):
            valor *= 1_000_000
        elif escala in ("mil", "k"):
            valor *= 1000
        if valor >= 1000:
            return _pesos(valor)
    return None


def _sumar_meses(d: date, meses: int) -> date:
    mes = d.month - 1 + meses
    anio, mes = d.year + mes // 12, mes % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def fecha_limite_en(texto: str, today: date) -> date | None:
    """ "en marzo" → último día del próximo marzo; "el 15 de marzo" → ese día; "en 3 meses" / "en 6 semanas" →
    hoy más ese tiempo. None si el texto no dice cuándo."""
    plano = sin_tildes(texto.lower())
    if m := re.search(r"(?:en|dentro de|in)\s+(\d{1,2})\s+(meses|mes|months|month)", plano):
        return _sumar_meses(today, int(m.group(1)))
    if m := re.search(r"(?:en|dentro de|in)\s+(\d{1,2})\s+(semanas|semana|weeks|week)", plano):
        return today + timedelta(weeks=int(m.group(1)))
    for nombre, numero in _MESES.items():
        m = re.search(rf"(?:(\d{{1,2}})\s+de\s+)?\b{nombre}\b", plano)
        if not m:
            continue
        anio = today.year if numero >= today.month else today.year + 1
        ultimo = calendar.monthrange(anio, numero)[1]
        dia = min(int(m.group(1)), ultimo) if m.group(1) else ultimo
        fecha = date(anio, numero, dia)
        return fecha if fecha > today else date(anio + 1, numero, dia)
    return None


_NOMBRE_META = re.compile(
    r"\b(?:para|for)\s+(?:un|una|el|la|mi|mis|los|las|a|an|my|the)?\s*([a-zñ ]{3,40}?)"
    r"(?=\s+(?:en|para|antes|de aqui|dentro|in|by|before)\b|[,.;:?!]|$)"
)


def nombre_de_meta(texto: str) -> str | None:
    """ "ahorrar 2 millones para un viaje en marzo" → "Viaje". None si no se entiende para qué es."""
    plano = sin_tildes(texto.lower())
    for m in _NOMBRE_META.finditer(plano):
        nombre = m.group(1).strip()
        if nombre and nombre not in _MESES and not re.fullmatch(r"(el|la|fin de)?\s*\w*\s*(mes|ano|year)", nombre):
            return nombre[:1].upper() + nombre[1:]
    return None


_INTENCION_META = re.compile(r"\b(ahorrar|ahorro para|juntar|reunir|save|saving for)\b")
_INTENCION_COMPRA = re.compile(
    r"\b(si (compro|gasto|pago)|puedo (comprar|gastar|pagar)|me alcanza|alcanza para|quiero (comprar|gastar)"
    r"|tengo que (comprar|pagar|gastar)|voy a (comprar|gastar|pagar)|comprar|compro|can i (buy|afford|spend)"
    r"|if i (buy|spend))\b"
)


def intencion(texto: str) -> str | None:
    """ "meta", "compra" o None: qué simulación pide un mensaje del chat (si trae un monto)."""
    plano = sin_tildes(texto.lower())
    if monto_en(texto) is None:
        return None
    if _INTENCION_META.search(plano):
        return "meta"
    if _INTENCION_COMPRA.search(plano):
        return "compra"
    return None
