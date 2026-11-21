"""Coach financiero: redacta mensajes con IA sobre cifras ya calculadas
(`patterns.py`, `budget_totals.py`). Cada salida de la IA pasa por un filtro
de guardrails y tiene un texto de respaldo determinista, así el coach nunca
deja de responder ni rompe sus reglas aunque el modelo falle."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import partial

from sqlmodel import Session, func, select

from app.core.time import fmt_fecha
from app.models.budget import Budget
from app.models.category import Category
from app.models.coach import CoachMessage
from app.models.expense import Expense
from app.models.goal import Goal, GoalContribution
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.services import ia_uso, previstos, simulador
from app.services import recurring_expenses as gastos_fijos
from app.services.budget_calculator import BudgetSummary
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import gasto_entre, summary_for
from app.services.groq_client import (
    MAX_DESCRIPCION,
    CupoIAAgotado,
    GroqServiceError,
    _extraer_json,
    generate_coach_json,
    generate_coach_text,
)
from app.services.ia_seguridad import (
    como_datos,
    filtra_salida,
    marca_inyeccion,
    parece_codigo,
    pedido_ajeno,
    sanear_dato,
    sin_tildes,
)
from app.services.patterns import Pattern, detect_patterns, fmt
from app.services.prompts import (
    build_coach_chat_prompt,
    build_coach_insights_prompt,
    build_coach_reaction_prompt,
    build_coach_rules,
)

HISTORIAL_CHAT = 10
# `id` de un mensaje del chat que no se guardó. Es el mismo valor con el que la app marca sus mensajes locales.
SIN_GUARDAR = -1

logger = logging.getLogger(__name__)

# Guardrails sobre la salida del modelo (en minúsculas). Si aparece alguno, el
# mensaje se descarta y se usa el texto de respaldo.
_LENGUAJE_CULPOSO = (
    "deberías avergonzarte", "qué vergüenza", "es tu culpa", "irresponsable", "despilfarr", "malgast",
    "derroch", "no tienes control", "you should be ashamed", "your fault", "irresponsible", "wasteful",
)
_ASESORIA_REGULADA = (
    "compra acciones", "invierte en", "te recomiendo invertir", "bitcoin", "criptomoneda", "cripto",
    "buy stocks", "invest in", "crypto",
)

_RESPALDO = {
    "es": {
        "reaccion": "¡Anotado! Registrar cada gasto es lo que te mantiene al mando. Te quedan {por_dia} por día.",
        "reaccion_sin_presupuesto": "¡Anotado! Registrar cada gasto es lo que te mantiene al mando.",
        "chat": "Ahora mismo no puedo responder con detalle, pero aquí va lo esencial: {contexto}",
        "inversion": "Sobre inversiones solo puedo darte educación general, no asesoría financiera. Lo que sí "
        "puedo hacer es ayudarte a organizar tu presupuesto y tus metas de ahorro.",
        "fuera_de_alcance": "Solo puedo ayudarte con tus finanzas dentro de Pay&Check: tu presupuesto, tus gastos "
        "y tus metas de ahorro. ¿Quieres que revisemos alguno de ellos?",
        "sin_cupo": "Este mes ya usaste todas tus solicitudes de IA, así que no puedo responder con detalle. "
        "Esto es lo esencial: {contexto}",
        "sin_cupo_corto": "Este mes ya usaste todas tus solicitudes de IA, pero esto sí te lo puedo decir:",
    },
    "en": {
        "reaccion": "Logged! Tracking every expense is what keeps you in charge. You have {por_dia} left per day.",
        "reaccion_sin_presupuesto": "Logged! Tracking every expense is what keeps you in charge.",
        "chat": "I can't answer in detail right now, but here is the essential: {contexto}",
        "inversion": "On investments I can only offer general education, not financial advice. What I can do "
        "is help you organize your budget and your savings goals.",
        "fuera_de_alcance": "I can only help you with your finances inside Pay&Check: your budget, your expenses "
        "and your savings goals. Want to go over any of them?",
        "sin_cupo": "You've used all your AI requests for this month, so I can't answer in detail. "
        "Here is the essential: {contexto}",
        "sin_cupo_corto": "You've used all your AI requests for this month, but this I can tell you:",
    },
}


def _respaldo(user: User, clave: str, **kwargs) -> str:
    # Por aquí pasan los textos de respaldo del coach: se llama solo cuando ese texto es el que se muestra,
    # y se anota en el registro de uso. La frase de redirección no es un respaldo: la mide `bloqueado_por`.
    if clave != "fuera_de_alcance":
        ia_uso.marcar_respaldo()
    return _RESPALDO.get(user.idioma, _RESPALDO["es"])[clave].format(**kwargs)


def _respaldo_texto(user: User, clave: str) -> str:
    """Un texto fijo sin anotarlo en el registro de uso (quien lo usa ya lo anotó)."""
    return _RESPALDO.get(user.idioma, _RESPALDO["es"])[clave]


def reglas_para(user: User) -> str:
    return build_coach_rules(user.nombre, user.coach_tone, user.idioma)


def rompe_guardrails(texto: str) -> str | None:
    """Devuelve "culpa", "inversion" o "salida" (fuga del prompt, URL, código o HTML, texto excesivo) si
    el texto rompe una regla del coach."""
    minusculas = texto.lower()
    if any(frase in minusculas for frase in _LENGUAJE_CULPOSO):
        return "culpa"
    if any(frase in minusculas for frase in _ASESORIA_REGULADA):
        return "inversion"
    if filtra_salida(texto):
        return "salida"
    return None


# "2 000 000" (con espacios, finos o normales, como a veces escribe el modelo) es una sola cifra.
_CIFRA = re.compile(r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d[\d.,]*")


def _cifras(texto: str) -> set[str]:
    """Las cifras de un texto, sin separadores: "9.625" y "9625" son la misma."""
    return {re.sub(r"\D", "", c) for c in _CIFRA.findall(texto)}


def inventa_cifras(mensaje: str, fuente: str) -> bool:
    """La IA redacta, no calcula: un consejo no puede traer montos ni porcentajes que no estén en el dato
    del que parte. Los números de una sola cifra ("2 frases", "1 día") no cuentan."""
    return any(len(c) >= 2 for c in _cifras(mensaje) - _cifras(fuente))


@dataclass
class Cifras:
    """Las cifras de la persona que el chat puede citar. Todas se calculan aquí: la IA no hace cuentas, así que
    cualquier dato que alguien pueda preguntar ("¿cuánto puedo gastar por semana?") tiene que venir ya hecho."""

    hoy: date
    presupuesto: Budget | None = None
    resumen: BudgetSummary | None = None
    # Lo que puede gastar en una semana. Si quedan menos de 7 días, es todo lo que queda hasta el cierre.
    por_semana: Decimal | None = None
    gastado_semana: Decimal = Decimal("0")
    gastado_mes: Decimal = Decimal("0")
    por_categoria: list[tuple[str, Decimal]] = field(default_factory=list)
    metas: list[tuple[str, Decimal, Decimal, date | None]] = field(default_factory=list)  # nombre, objetivo, ahorrado
    fijos: list[tuple[str, Decimal, date, bool]] = field(default_factory=list)  # descripción, monto, fecha, vencido


def cifras_de(session: Session, user: User, today: date) -> Cifras:
    cifras = Cifras(hoy=today)
    lunes = today - timedelta(days=today.weekday())
    cifras.gastado_semana = gasto_entre(session, user.id, lunes, today)
    cifras.gastado_mes = gasto_entre(session, user.id, today.replace(day=1), today)

    budget = get_active_budget_for_user(session, user.id, today)
    if budget is not None:
        s = summary_for(session, budget, today)
        cifras.presupuesto, cifras.resumen = budget, s
        if s.dias_restantes >= 7:
            cifras.por_semana = s.disponible_por_semana
        elif s.dias_restantes > 0:
            cifras.por_semana = s.disponible_total
        cifras.por_categoria = [
            (sanear_dato(nombre), Decimal(total))
            for nombre, total in session.exec(
                select(Category.nombre, func.sum(Expense.monto))
                .join(Category, Category.id == Expense.category_id)
                .where(Expense.budget_id == budget.id)
                .group_by(Category.nombre)
                .order_by(func.sum(Expense.monto).desc())
                .limit(5)
            ).all()
        ]

    for meta in session.exec(select(Goal).where(Goal.user_id == user.id).where(Goal.estado == "activa")).all():
        ahorrado = Decimal(
            session.exec(
                select(func.coalesce(func.sum(GoalContribution.monto), 0)).where(GoalContribution.goal_id == meta.id)
            ).one()
        )
        cifras.metas.append((sanear_dato(meta.nombre), meta.monto_objetivo, ahorrado, meta.fecha_limite))

    vencidos = gastos_fijos.pendientes(session, user.id, today)
    cifras.fijos = [(sanear_dato(r.descripcion), r.monto, f, True) for r, f in vencidos]
    ya_listados = {r.id for r, _ in vencidos}
    for r in session.exec(select(RecurringExpense).where(RecurringExpense.user_id == user.id)).all():
        if r.activo and r.id not in ya_listados:
            proximo = gastos_fijos.proximo_vencimiento(r, today)
            if proximo <= today + timedelta(days=7):
                cifras.fijos.append((sanear_dato(r.descripcion), r.monto, proximo, False))
    return cifras


def contexto_financiero(
    session: Session,
    user: User,
    today: date,
    patrones: list[Pattern] | None = None,
    *,
    detalle: bool = True,
    cifras: Cifras | None = None,
) -> str:
    """Situación del usuario en texto compacto y agregado para la IA. Con `detalle=False` es la versión corta
    que se le muestra a la persona en un texto de respaldo."""
    # Fechas en palabras: el modelo las repite tal cual en lo que redacta.
    idioma = user.idioma
    c = cifras or cifras_de(session, user, today)
    f = partial(fmt_fecha, idioma=idioma, con_anio=True)
    lineas = [f"Fecha de hoy: {f(today)}"]

    budget, s = c.presupuesto, c.resumen
    if budget is None or s is None:
        lineas.append("No tiene un presupuesto activo.")
    else:
        lineas += [
            f"Presupuesto del periodo ({f(budget.fecha_inicio)} a {f(budget.fecha_fin)}): {fmt(budget.monto_total)}",
            f"Gastado: {fmt(s.gastado_total)}. Ingresos extra: {fmt(s.ingresos_total)}. "
            f"Apartado para metas: {fmt(s.apartado_total)}.",
            f"Disponible: {fmt(s.disponible_total)} ({fmt(s.disponible_por_dia)} por día, "
            f"{s.dias_restantes} días restantes).",
        ]
    if not detalle:
        return "\n".join(lineas)

    lineas.append("Cifras ya calculadas (úsalas tal cual cuando te pregunten por ellas):")
    if s is not None:
        if c.por_semana is not None and s.dias_restantes >= 7:
            lineas.append(f"  - Disponible para gastar por semana: {fmt(c.por_semana)}.")
        elif c.por_semana is not None:
            lineas.append(
                f"  - Disponible para gastar esta semana: {fmt(c.por_semana)} (es todo lo que queda hasta el "
                f"cierre del presupuesto, en {s.dias_restantes} días)."
            )
        lineas.append(f"  - Disponible para gastar por día: {fmt(s.disponible_por_dia)}.")
        lineas.append(f"  - Disponible en total hasta el {f(budget.fecha_fin)}: {fmt(s.disponible_total)}.")
        if s.en_riesgo and s.fecha_proyectada_agotamiento:
            lineas.append(
                f"  - Al ritmo de gasto actual el dinero alcanza hasta el {f(s.fecha_proyectada_agotamiento)}, "
                f"antes del cierre del presupuesto."
            )
        elif s.gastado_total > 0:
            lineas.append("  - Al ritmo de gasto actual el dinero alcanza hasta el cierre del presupuesto.")
    lineas.append(f"  - Gastado esta semana (desde el lunes): {fmt(c.gastado_semana)}.")
    lineas.append(f"  - Gastado este mes: {fmt(c.gastado_mes)}.")
    if c.por_categoria:
        total_cat = sum((t for _, t in c.por_categoria), Decimal("0")) or Decimal("1")
        lineas.append(
            "  - Gasto del periodo por categoría (solo existen estas; no nombres otras): "
            + ", ".join(
                f"{nombre} {fmt(total)} ({int((total * 100 / total_cat).to_integral_value())} %)"
                for nombre, total in c.por_categoria
            )
            + "."
        )
    for nombre, objetivo, ahorrado, limite in c.metas:
        falta = max(objetivo - ahorrado, Decimal("0"))
        hasta = f", fecha límite {f(limite)}" if limite else ""
        lineas.append(
            f"  - Meta de ahorro activa: {nombre}: objetivo {fmt(objetivo)}, ahorrado {fmt(ahorrado)}, "
            f"falta {fmt(falta)}{hasta}."
        )
    proximos = previstos.proximos(session, user, today)
    for previsto in proximos:
        lineas.append(
            f"  - Gasto grande previsto: {sanear_dato(previsto.gasto.descripcion)}, {fmt(previsto.gasto.monto)}, "
            f"el {f(previsto.gasto.fecha)} (en {previsto.dias} días): apartar {fmt(previsto.por_semana)} por semana "
            "lo cubre."
        )
    if proximos and budget is not None:
        total, queda = previstos.total_por_semana(proximos, c.por_semana)
        lineas.append(f"  - Total a apartar por semana para gastos que vienen: {fmt(total)}.")
        if queda is not None and queda >= 0:
            lineas.append(f"  - Te queda por semana después de apartarlo: {fmt(queda)}.")
        elif queda is not None:  # los montos van sin signo menos: el sentido va en palabras
            lineas.append(
                f"  - Con tu ritmo actual te faltan {fmt(-queda)} por semana para poder apartarlo todo."
            )
    for descripcion, monto, fecha, vencido in c.fijos:
        estado = "vencido y por pagar desde" if vencido else "vence el"
        lineas.append(f"  - Gasto fijo {descripcion}: {fmt(monto)}, {estado} {f(fecha)}.")

    patrones = detect_patterns(session, user, today) if patrones is None else patrones
    if patrones:
        lineas.append("Patrones detectados:")
        lineas += [f"  - {p.descripcion}" for p in patrones]
    return "\n".join(lineas)


_PREGUNTA_DISPONIBLE = re.compile(
    r"(cuanto|cuanta plata|cuanto dinero|how much).{0,40}"
    r"(tengo|me queda|quedan|puedo gastar|disponible|gastar|left|can i spend|available|budget)"
)
_PERIODO = (
    ("semana", re.compile(r"seman|week")),
    ("dia", re.compile(r"\bdia|diari|\bday|daily|hoy\b|today")),
)


def respuesta_de_disponible(user: User, mensaje: str, cifras: Cifras) -> str | None:
    """Respuesta determinista a "¿cuánto puedo gastar (por día | por semana | en total)?", o None si el mensaje
    no pregunta eso. Sirve de respaldo cuando la IA no responde o no da la cifra: esa pregunta siempre tiene
    una respuesta concreta."""
    plano = sin_tildes(mensaje.lower())
    if not _PREGUNTA_DISPONIBLE.search(plano):
        return None
    periodo = next((nombre for nombre, patron in _PERIODO if patron.search(plano)), "total")
    en = user.idioma == "en"
    budget, s = cifras.presupuesto, cifras.resumen
    if budget is None or s is None:
        return (
            "You don't have an active budget yet, so there's no available amount to work out. Create one in "
            "the Budget tab and I'll tell you how much you can spend per day and per week."
            if en
            else "Aún no tienes un presupuesto activo, así que no hay un disponible que calcular. Crea uno en la "
            "pestaña Presupuesto y te digo cuánto puedes gastar por día y por semana."
        )
    fin = fmt_fecha(budget.fecha_fin, user.idioma)
    total, por_dia, dias = fmt(s.disponible_total), fmt(s.disponible_por_dia), s.dias_restantes
    if dias == 0:
        return (
            f"Your budget closed on {fin} with {total} left. Create a new one and I'll tell you how much you can spend."
            if en
            else f"Tu presupuesto cerró el {fin} y te quedaron {total}. Crea uno nuevo y te digo cuánto puedes gastar."
        )
    if periodo == "semana" and dias >= 7:
        return (
            f"You can spend {fmt(cifras.por_semana)} per week until {fin} ({dias} days left). That's {por_dia} "
            f"per day, and {total} in total."
            if en
            else f"Puedes gastar {fmt(cifras.por_semana)} por semana hasta el {fin} (quedan {dias} días). Eso es "
            f"{por_dia} por día y {total} en total."
        )
    if periodo == "semana":
        return (
            f"Your budget closes on {fin}, in {dias} days, so this week you can spend everything left: {total} "
            f"({por_dia} per day)."
            if en
            else f"Tu presupuesto cierra el {fin}, en {dias} días, así que esta semana puedes gastar todo lo que "
            f"queda: {total} ({por_dia} por día)."
        )
    if periodo == "dia":
        return (
            f"You can spend {por_dia} per day for the {dias} days left (until {fin})."
            if en
            else f"Puedes gastar {por_dia} por día durante los {dias} días que quedan (hasta el {fin})."
        )
    return (
        f"You have {total} available until {fin} ({por_dia} per day for {dias} days)."
        if en
        else f"Tienes {total} disponibles hasta el {fin} ({por_dia} por día durante {dias} días)."
    )


@dataclass
class Simulacion:
    """Lo que el chat sabe responder con cuentas propias: el texto directo (respaldo y fuente de cifras para el
    modelo) y la acción de un toque que la app muestra debajo de la respuesta."""

    texto: str
    accion: dict | None


def simulacion_de_chat(user: User, mensaje: str, cifras: Cifras) -> Simulacion | None:
    """ "Quiero ahorrar 2 millones para un viaje en marzo" o "si compro 350.000 en ropa…": la cuenta la hace
    `services/simulador.py`, nunca el modelo. None si el mensaje no pide una simulación."""
    tipo = simulador.intencion(mensaje)
    if tipo is None:
        return None
    en = user.idioma == "en"
    monto = simulador.monto_en(mensaje)
    hoy = cifras.hoy
    f = partial(fmt_fecha, idioma=user.idioma, con_anio=True)
    s = cifras.resumen

    if tipo == "meta":
        limite = simulador.fecha_limite_en(mensaje, hoy)
        nombre = simulador.nombre_de_meta(mensaje) or ("My goal" if en else "Mi meta")
        plan = simulador.plan_de_meta(monto, Decimal("0"), limite, hoy)
        accion = {
            "tipo": "crear_meta",
            "etiqueta": f"Create goal: {nombre}" if en else f"Crear meta: {nombre}",
            "payload": {
                "nombre": nombre,
                "monto_objetivo": str(monto),
                "fecha_limite": limite.isoformat() if limite else None,
            },
        }
        if plan.por_semana is None:
            texto = (
                f"To save {fmt(monto)} for {nombre.lower()}, tell me by when and I'll work out how much to set "
                f"aside each week. I can create the goal now if you want."
                if en
                else f"Para juntar {fmt(monto)} para {nombre.lower()}, dime para cuándo y te digo cuánto apartar "
                f"cada semana. Si quieres, creo la meta ya."
            )
            return Simulacion(texto, accion)
        texto = (
            f"To save {fmt(monto)} for {nombre.lower()} by {f(limite)}, set aside {fmt(plan.por_semana)} per "
            f"week ({fmt(plan.por_dia)} per day)."
            if en
            else f"Para juntar {fmt(monto)} para {nombre.lower()} antes del {f(limite)}, aparta "
            f"{fmt(plan.por_semana)} por semana ({fmt(plan.por_dia)} por día)."
        )
        if cifras.por_semana is not None and s is not None and s.dias_restantes >= 7:
            resto = cifras.por_semana - plan.por_semana
            if resto >= 0:
                texto += (
                    f" Today you can spend {fmt(cifras.por_semana)} per week, so after setting that aside you'd "
                    f"still have {fmt(resto)} per week for your expenses."
                    if en
                    else f" Hoy puedes gastar {fmt(cifras.por_semana)} por semana: después de apartar eso te "
                    f"quedarían {fmt(resto)} por semana para tus gastos."
                )
            else:
                texto += (
                    f" That's more than the {fmt(cifras.por_semana)} per week your current budget allows: you'd "
                    f"need {fmt(-resto)} more per week, or a later date."
                    if en
                    else f" Es más de los {fmt(cifras.por_semana)} por semana que te deja tu presupuesto actual: "
                    f"te faltarían {fmt(-resto)} por semana, o una fecha más lejana."
                )
        texto += " Shall I create the goal?" if en else " ¿Creamos la meta?"
        return Simulacion(texto, accion)

    # Compra
    if cifras.presupuesto is None or s is None or s.dias_restantes == 0:
        return None  # sin presupuesto vigente no hay nada que simular: responde el flujo normal
    meta_plan = meta_nombre = None
    for nombre_meta, objetivo, ahorrado, limite in cifras.metas:
        candidato = simulador.plan_de_meta(objetivo, ahorrado, limite, hoy)
        if candidato.por_dia:
            meta_plan, meta_nombre = candidato, nombre_meta
            break
    sim = simulador.simular_compra(cifras.presupuesto, s, monto, hoy, meta_plan, meta_nombre)
    d = sim.despues
    if not sim.alcanza:
        texto = (
            f"If you spend {fmt(monto)} today you'd go {fmt(-d.disponible_total)} over your budget, which has "
            f"{fmt(s.disponible_total)} left until {f(cifras.presupuesto.fecha_fin)}."
            if en
            else f"Si hoy gastas {fmt(monto)} te pasarías {fmt(-d.disponible_total)} de tu presupuesto, al que "
            f"le quedan {fmt(s.disponible_total)} hasta el {f(cifras.presupuesto.fecha_fin)}."
        )
    else:
        texto = (
            f"If you spend {fmt(monto)} today, your daily amount goes from {fmt(s.disponible_por_dia)} to "
            f"{fmt(d.disponible_por_dia)} for the {d.dias_restantes} days left."
            if en
            else f"Si hoy gastas {fmt(monto)}, tu disponible por día baja de {fmt(s.disponible_por_dia)} a "
            f"{fmt(d.disponible_por_dia)} durante los {d.dias_restantes} días que quedan."
        )
        if d.en_riesgo and d.fecha_proyectada_agotamiento:
            texto += (
                f" At that pace the money would last until {f(d.fecha_proyectada_agotamiento)}."
                if en
                else f" A ese ritmo el dinero alcanzaría hasta el {f(d.fecha_proyectada_agotamiento)}."
            )
    if sim.meta_dias_equivalentes:
        texto += (
            f" It equals {sim.meta_dias_equivalentes} days of saving for {sim.meta_nombre}."
            if en
            else f" Equivale a {sim.meta_dias_equivalentes} días de ahorro para tu meta {sim.meta_nombre}."
        )
    accion = {
        "tipo": "registrar_gasto",
        "etiqueta": "Log this expense" if en else "Registrar este gasto",
        "payload": {"monto": str(monto)},
    }
    return Simulacion(texto, accion)


def reaccion_a_gasto(session: Session, user: User, expense: Expense, today: date) -> str:
    """Mensaje corto y sin culpa tras registrar un gasto (C-01)."""
    budget = get_active_budget_for_user(session, user.id, today)
    # Perezoso: `_respaldo` se anota en el registro de uso, así que solo se llama si ese texto se muestra.
    if budget is None:
        respaldo = partial(_respaldo, user, "reaccion_sin_presupuesto")
        disponible = "Sin presupuesto activo."
    else:
        s = summary_for(session, budget, today)
        respaldo = partial(_respaldo, user, "reaccion", por_dia=fmt(s.disponible_por_dia))
        disponible = f"Disponible por día: {fmt(s.disponible_por_dia)}. Días restantes: {s.dias_restantes}."
        if s.en_riesgo and s.fecha_proyectada_agotamiento:
            # Sin esto la reacción decía "se ajusta bien" mientras Inicio avisaba que el dinero no alcanza.
            fecha = fmt_fecha(s.fecha_proyectada_agotamiento, user.idioma)
            disponible += (
                f" Ojo: al ritmo actual el dinero alcanza hasta el {fecha}, antes del cierre del presupuesto; no "
                "digas que el gasto se ajusta bien, invita con calma a cuidar los próximos días."
            )

    categoria = session.get(Category, expense.category_id)
    meta = session.exec(select(Goal).where(Goal.user_id == user.id).where(Goal.estado == "activa")).first()
    contexto = "\n".join(
        [
            f"Gasto registrado: {sanear_dato(expense.descripcion, MAX_DESCRIPCION)}, {fmt(expense.monto)}, "
            f"categoría {sanear_dato(categoria.nombre) if categoria else 'otros'}.",
            disponible,
            f"Meta de ahorro activa: {sanear_dato(meta.nombre)}." if meta else "Sin meta de ahorro activa.",
        ]
    )

    with ia_uso.usar(session, user, "reaccion"):
        try:
            mensaje = generate_coach_text(build_coach_reaction_prompt(reglas_para(user), contexto))
        except GroqServiceError:
            return respaldo()
        # El disponible por día ya descuenta este gasto: si la IA resta o suma por su cuenta, el dato sale mal.
        if not mensaje or rompe_guardrails(mensaje) or inventa_cifras(mensaje, contexto):
            return respaldo()
    return mensaje


def _redactar_insights(user: User, patrones: list[Pattern]) -> list[str]:
    """Un mensaje por patrón. Ante cualquier fallo o salida inválida de la IA,
    cada patrón conserva su descripción determinista."""
    respaldo = [p.descripcion for p in patrones]
    numerados = "\n".join(f"{i}. {p.descripcion}" for i, p in enumerate(patrones, start=1))
    try:
        data = generate_coach_json(build_coach_insights_prompt(reglas_para(user)), numerados)
    except GroqServiceError:
        ia_uso.marcar_respaldo()
        return respaldo

    mensajes = data.get("mensajes")
    if not isinstance(mensajes, list) or len(mensajes) != len(patrones):
        ia_uso.marcar_respaldo()
        return respaldo
    redactados = [
        mensaje
        if isinstance(mensaje, str)
        and mensaje.strip()
        and not rompe_guardrails(mensaje)
        and not inventa_cifras(mensaje, original)
        else original
        for mensaje, original in zip(mensajes, respaldo, strict=True)
    ]
    if any(redactado is original for redactado, original in zip(redactados, respaldo, strict=True)):
        ia_uso.marcar_respaldo()
    return redactados


def insights_del_dia(session: Session, user: User, today: date, refresh: bool = False) -> list[dict]:
    """Consejos accionables del día (C-04). Se cachean por día, tono e idioma
    para no gastar una llamada a la IA en cada apertura de la app."""
    # La firma incluye qué patrones hay (y la fecha de agotamiento, si la hay): si cambian durante el día, el
    # consejo guardado ya no coincide con el aviso de Inicio y se vuelve a redactar.
    patrones = detect_patterns(session, user, today)
    firma = {
        "tono": user.coach_tone,
        "idioma": user.idioma,
        "patrones": [p.descripcion if p.tipo == "en_riesgo" else p.tipo for p in patrones],
    }
    cache = session.exec(
        select(CoachMessage)
        .where(CoachMessage.user_id == user.id)
        .where(CoachMessage.tipo == "insights")
        .where(CoachMessage.fecha == today)
    ).first()

    if cache is not None and not refresh:
        guardado = json.loads(cache.contenido)
        if guardado.get("firma") == firma:
            return guardado["insights"]

    if patrones:
        with ia_uso.usar(session, user, "consejos"):
            mensajes = _redactar_insights(user, patrones)
    else:
        mensajes = []
    insights = [
        {**asdict(patron), "mensaje": mensaje} for patron, mensaje in zip(patrones, mensajes, strict=True)
    ]

    contenido = json.dumps({"firma": firma, "insights": insights}, ensure_ascii=False)
    if cache is None:
        cache = CoachMessage(user_id=user.id, tipo="insights", contenido=contenido, fecha=today)
    else:
        cache.contenido = contenido
    session.add(cache)
    session.commit()
    return insights


def historial_chat(session: Session, user_id: int, limite: int = 50) -> list[CoachMessage]:
    mensajes = session.exec(
        select(CoachMessage)
        .where(CoachMessage.user_id == user_id)
        .where(CoachMessage.tipo.in_(("chat_user", "chat_coach")))
        .order_by(CoachMessage.id.desc())
        .limit(limite)
    ).all()
    return list(reversed(mensajes))


def _leer_turno(raw: str) -> tuple[bool, str] | None:
    """Lee el contrato {"en_alcance", "respuesta"} del chat. None si el modelo no lo cumplió."""
    try:
        data = _extraer_json(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("en_alcance"), bool):
        return None
    respuesta = data.get("respuesta")
    return data["en_alcance"], respuesta.strip() if isinstance(respuesta, str) else ""


# Frases con las que el modelo le devuelve la cuenta a la persona en vez de darle la cifra.
_PIDE_LA_CUENTA = re.compile(
    r"haz la cuenta|haces la cuenta|calcula(lo)? tu|calculalo|divide (tu|el|ese|lo)|dividelo|dividir (tu|el|ese)"
    r"|multiplica (tu|el|ese)|toma (tu|el) (disponible|valor|total)|do the math|divide (your|the|it)"
    r"|multiply (your|the)|calculate it yourself"
)


def pide_la_cuenta(texto: str) -> bool:
    return bool(_PIDE_LA_CUENTA.search(sin_tildes(texto.lower())))


def _es_redireccion(texto: str) -> bool:
    return texto in (r["fuera_de_alcance"] for r in _RESPALDO.values())


def _previos(session: Session, user: User) -> list[dict]:
    """Los últimos turnos del chat para el modelo. Los que terminaron en la frase de redirección no se
    reenvían: un pedido ajeno (o un ataque) no debe quedar como contexto de los siguientes. Lo que escribió la
    persona viaja siempre como dato, así una inyección guardada antes no queda "viva" como instrucción."""
    mensajes = historial_chat(session, user.id, HISTORIAL_CHAT)
    previos: list[dict] = []
    for i, m in enumerate(mensajes):
        if m.tipo == "chat_user":
            siguiente = mensajes[i + 1] if i + 1 < len(mensajes) else None
            if siguiente is not None and siguiente.tipo == "chat_coach" and _es_redireccion(siguiente.contenido):
                continue
            previos.append({"role": "user", "content": como_datos(m.contenido)})
        elif not _es_redireccion(m.contenido):
            previos.append({"role": "assistant", "content": m.contenido})
    return previos


def _guardar_turno(session: Session, user: User, mensaje: str, respuesta: str, today: date) -> CoachMessage:
    session.add(CoachMessage(user_id=user.id, tipo="chat_user", contenido=mensaje, fecha=today))
    del_coach = CoachMessage(user_id=user.id, tipo="chat_coach", contenido=respuesta, fecha=today)
    session.add(del_coach)
    session.commit()
    session.refresh(del_coach)
    return del_coach


def responder_chat(session: Session, user: User, mensaje: str, today: date) -> tuple[CoachMessage, dict | None]:
    """Responde un turno del chat y guarda ambos mensajes. Nunca lanza GroqServiceError: si Groq está caído,
    limitado o no responde, o si se agotó el cupo mensual, contesta con el texto de respaldo pero NO guarda el
    turno. El historial se reenvía al modelo y no debe llevar textos de respaldo; el mensaje devuelto trae
    `id` = SIN_GUARDAR.

    Capas (planFinal §4.1):
    1. Un pedido claramente ajeno (código, juegos, poemas, tareas…) se rechaza aquí, sin llamar a Groq.
    2. El modelo devuelve {"en_alcance", "respuesta"}: si el tema es ajeno la `respuesta` se ignora y se
       muestra la frase fija de redirección, así el rechazo no depende de que el modelo se porte bien.
    3. La respuesta pasa por los filtros de salida; si trae código, también se redirige.
    Las cifras las calcula el backend (`cifras_de`): a "¿cuánto puedo gastar por semana?" siempre se responde
    con la cifra, del modelo o de `respuesta_de_disponible`. Lo mismo con las simulaciones ("si compro X",
    "quiero ahorrar X para Y"): las calcula `simulacion_de_chat` y además devuelven una acción de un toque, que
    acompaña la respuesta pero no se guarda."""
    if pedido_ajeno(mensaje):
        # Se deja la fila en el registro de uso para medir los bloqueos; no es una llamada exitosa, así que no
        # gasta cupo. Si además parece un intento de inyección, se cuenta como tal (es lo más grave).
        motivo = "inyeccion" if marca_inyeccion(mensaje) else "alcance"
        with ia_uso.usar(session, user, "chat"):
            if contexto := ia_uso.actual():
                ia_uso.registrar(contexto, "filtro_local", exito=False, bloqueado_por=motivo)
        return _guardar_turno(session, user, mensaje, _respaldo(user, "fuera_de_alcance"), today), None

    inyectado = marca_inyeccion(mensaje)
    if inyectado:
        logger.warning("coach/chat: el mensaje parece un intento de inyección")
    cifras = cifras_de(session, user, today)
    sim = simulacion_de_chat(user, mensaje, cifras)
    accion = sim.accion if sim else None
    directa = sim.texto if sim else respuesta_de_disponible(user, mensaje, cifras)
    contexto = contexto_financiero(session, user, today, cifras=cifras)
    if sim:
        contexto += (
            "\nSimulación ya calculada para el último mensaje (responde con estas cifras tal cual, sin hacer "
            f"otras cuentas):\n  - {sim.texto}"
        )
    corto = partial(contexto_financiero, session, user, today, patrones=[], detalle=False, cifras=cifras)
    prompt = build_coach_chat_prompt(reglas_para(user), contexto)
    turnos = [*_previos(session, user), {"role": "user", "content": como_datos(mensaje)}]
    with ia_uso.usar(session, user, "chat"):
        sin_cupo = caida = False
        try:
            raw = generate_coach_text(prompt, turnos)
        except CupoIAAgotado:
            raw, sin_cupo = None, True
        except GroqServiceError:
            raw, caida = None, True
        finally:
            if inyectado:
                ia_uso.marcar_bloqueo("inyeccion")
        caida = caida or (raw is not None and not raw)  # Groq respondió, pero sin nada

        if caida or sin_cupo:
            if directa:
                ia_uso.marcar_respaldo()
                respuesta = f"{_respaldo_texto(user, 'sin_cupo_corto')} {directa}" if sin_cupo else directa
            else:
                respuesta = _respaldo(user, "sin_cupo" if sin_cupo else "chat", contexto=corto())
            sin_guardar = CoachMessage(
                id=SIN_GUARDAR, user_id=user.id, tipo="chat_coach", contenido=respuesta, fecha=today
            )
            return sin_guardar, accion

        # Una salida que no cumple el contrato queda como respuesta vacía y cae al texto de respaldo.
        en_alcance, respuesta = _leer_turno(raw or "") or (True, "")

        if not en_alcance or (respuesta and parece_codigo(respuesta)):
            ia_uso.marcar_bloqueo("alcance")
            respuesta = _respaldo(user, "fuera_de_alcance")
        else:
            # Si trae cifras que no salen ni de sus datos ni de lo conversado, o le devuelve la cuenta a la
            # persona, se le pide una vez que responda con las cifras ya calculadas. No se descarta sin más: en
            # el chat la persona puede haber pedido una cuenta.
            conocido = "\n".join([contexto, *(t["content"] for t in turnos)])
            # Las cifras del mensaje ya están en `conocido` (van en los turnos). Una cuenta que la persona pida
            # y que no esté calculada no se acepta del modelo: se le pide repetir con las cifras que hay.
            inventa = respuesta and inventa_cifras(respuesta, conocido)
            if inventa or pide_la_cuenta(respuesta):
                turnos += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "Repite tu respuesta, en el mismo formato JSON. Usa solo las cifras de "
                        '"Cifras ya calculadas" de mi situación y dame la cifra directamente: no me pidas hacer '
                        "cuentas ni propongas montos o porcentajes nuevos.",
                    },
                ]
                try:
                    nuevo = _leer_turno(generate_coach_text(prompt, turnos))
                except GroqServiceError:
                    nuevo = None
                if nuevo and nuevo[0] and nuevo[1]:
                    respuesta = nuevo[1]
                if inventa_cifras(respuesta, conocido) or pide_la_cuenta(respuesta):
                    respuesta = ""  # sigue sin dar la cifra: cae al respaldo de abajo

            regla_rota = rompe_guardrails(respuesta) if respuesta else "vacia"
            if regla_rota == "inversion":
                respuesta = _respaldo(user, "inversion")
            elif regla_rota and parece_codigo(respuesta):
                ia_uso.marcar_bloqueo("alcance")
                respuesta = _respaldo(user, "fuera_de_alcance")
            elif regla_rota and directa:
                ia_uso.marcar_respaldo()
                respuesta = directa
            elif regla_rota:
                respuesta = _respaldo(user, "chat", contexto=corto())

    if _es_redireccion(respuesta):
        accion = None
    return _guardar_turno(session, user, mensaje, respuesta, today), accion
