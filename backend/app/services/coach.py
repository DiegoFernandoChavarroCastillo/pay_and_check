"""Coach financiero: redacta mensajes con IA sobre cifras ya calculadas
(`patterns.py`, `budget_totals.py`). Cada salida de la IA pasa por un filtro
de guardrails y tiene un texto de respaldo determinista, así el coach nunca
deja de responder ni rompe sus reglas aunque el modelo falle."""

import json
import logging
import re
from dataclasses import asdict
from datetime import date
from functools import partial

from sqlmodel import Session, select

from app.core.time import fmt_fecha
from app.models.category import Category
from app.models.coach import CoachMessage
from app.models.expense import Expense
from app.models.goal import Goal
from app.models.user import User
from app.services import ia_uso
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for
from app.services.groq_client import (
    MAX_DESCRIPCION,
    GroqServiceError,
    _extraer_json,
    generate_coach_json,
    generate_coach_text,
)
from app.services.ia_seguridad import como_datos, filtra_salida, marca_inyeccion, sanear_dato
from app.services.patterns import Pattern, detect_patterns, fmt
from app.services.prompts import (
    build_coach_chat_prompt,
    build_coach_insights_prompt,
    build_coach_reaction_prompt,
    build_coach_rules,
)

HISTORIAL_CHAT = 10

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
    },
    "en": {
        "reaccion": "Logged! Tracking every expense is what keeps you in charge. You have {por_dia} left per day.",
        "reaccion_sin_presupuesto": "Logged! Tracking every expense is what keeps you in charge.",
        "chat": "I can't answer in detail right now, but here is the essential: {contexto}",
        "inversion": "On investments I can only offer general education, not financial advice. What I can do "
        "is help you organize your budget and your savings goals.",
        "fuera_de_alcance": "I can only help you with your finances inside Pay&Check: your budget, your expenses "
        "and your savings goals. Want to go over any of them?",
    },
}


def _respaldo(user: User, clave: str, **kwargs) -> str:
    # Por aquí pasan los textos de respaldo del coach: se llama solo cuando ese texto es el que se muestra,
    # y se anota en el registro de uso. La frase de redirección no es un respaldo: la mide `bloqueado_por`.
    if clave != "fuera_de_alcance":
        ia_uso.marcar_respaldo()
    return _RESPALDO.get(user.idioma, _RESPALDO["es"])[clave].format(**kwargs)


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


_CIFRA = re.compile(r"\d[\d.,]*")


def _cifras(texto: str) -> set[str]:
    """Las cifras de un texto, sin separadores: "9.625" y "9625" son la misma."""
    return {re.sub(r"\D", "", c) for c in _CIFRA.findall(texto)}


def inventa_cifras(mensaje: str, fuente: str) -> bool:
    """La IA redacta, no calcula: un consejo no puede traer montos ni porcentajes que no estén en el dato
    del que parte. Los números de una sola cifra ("2 frases", "1 día") no cuentan."""
    return any(len(c) >= 2 for c in _cifras(mensaje) - _cifras(fuente))


def contexto_financiero(session: Session, user: User, today: date, patrones: list[Pattern] | None = None) -> str:
    """Situación del usuario en texto compacto y agregado para la IA."""
    # Fechas en palabras: el modelo las repite tal cual en lo que redacta.
    idioma = user.idioma
    lineas = [f"Fecha de hoy: {fmt_fecha(today, idioma, con_anio=True)}"]

    budget = get_active_budget_for_user(session, user.id, today)
    if budget is None:
        lineas.append("No tiene un presupuesto activo.")
    else:
        s = summary_for(session, budget, today)
        lineas += [
            f"Presupuesto del periodo ({fmt_fecha(budget.fecha_inicio, idioma, con_anio=True)} a "
            f"{fmt_fecha(budget.fecha_fin, idioma, con_anio=True)}): "
            f"{fmt(budget.monto_total)}",
            f"Gastado: {fmt(s.gastado_total)}. Ingresos extra: {fmt(s.ingresos_total)}. "
            f"Apartado para metas: {fmt(s.apartado_total)}.",
            f"Disponible: {fmt(s.disponible_total)} ({fmt(s.disponible_por_dia)} por día, "
            f"{s.dias_restantes} días restantes).",
        ]

    metas = session.exec(select(Goal).where(Goal.user_id == user.id).where(Goal.estado == "activa")).all()
    for meta in metas:
        lineas.append(f"Meta de ahorro activa: {sanear_dato(meta.nombre)} (objetivo {fmt(meta.monto_objetivo)}).")

    patrones = detect_patterns(session, user, today) if patrones is None else patrones
    if patrones:
        lineas.append("Patrones detectados:")
        lineas += [f"  - {p.descripcion}" for p in patrones]
    return "\n".join(lineas)


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
    firma = {"tono": user.coach_tone, "idioma": user.idioma}
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

    patrones = detect_patterns(session, user, today)
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


def responder_chat(session: Session, user: User, mensaje: str, today: date) -> CoachMessage:
    """Responde un turno del chat y guarda ambos mensajes. Lanza
    GroqServiceError si la IA no está disponible (no se guarda nada).

    El modelo devuelve {"en_alcance", "respuesta"}: si el tema es ajeno la `respuesta` se ignora y se
    muestra la frase fija de redirección, así el rechazo no depende de que el modelo se porte bien."""
    inyectado = marca_inyeccion(mensaje)
    if inyectado:
        logger.warning("coach/chat: el mensaje parece un intento de inyección")
    # Lo que escribió la persona viaja siempre como dato, también el historial: una inyección guardada
    # antes no queda "viva" como instrucción.
    previos = [
        {"role": "user", "content": como_datos(m.contenido)}
        if m.tipo == "chat_user"
        else {"role": "assistant", "content": m.contenido}
        for m in historial_chat(session, user.id, HISTORIAL_CHAT)
    ]
    contexto = contexto_financiero(session, user, today)
    prompt = build_coach_chat_prompt(reglas_para(user), contexto)
    turnos = [*previos, {"role": "user", "content": como_datos(mensaje)}]
    with ia_uso.usar(session, user, "chat"):
        try:
            raw = generate_coach_text(prompt, turnos)
        finally:
            if inyectado:
                ia_uso.marcar_bloqueo("inyeccion")
        # Una salida que no cumple el contrato queda como respuesta vacía y cae al texto de respaldo.
        en_alcance, respuesta = _leer_turno(raw) or (True, "")

        if not en_alcance:
            ia_uso.marcar_bloqueo("alcance")
            respuesta = _respaldo(user, "fuera_de_alcance")
        else:
            # Si trae cifras que no salen ni de sus datos ni de lo conversado, se le pide una vez que responda
            # sin ellas. No se descarta sin más: en el chat la persona puede haber pedido una cuenta.
            conocido = "\n".join([contexto, *(t["content"] for t in turnos)])
            if respuesta and inventa_cifras(respuesta, conocido) and not _CIFRA.search(mensaje):
                turnos += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "Repite tu respuesta, en el mismo formato JSON, sin proponer montos ni "
                        "porcentajes que no estén en mi situación: describe el paso con palabras.",
                    },
                ]
                try:
                    nuevo = _leer_turno(generate_coach_text(prompt, turnos))
                except GroqServiceError:
                    nuevo = None
                if nuevo and nuevo[0] and nuevo[1]:
                    respuesta = nuevo[1]

            regla_rota = rompe_guardrails(respuesta) if respuesta else "vacia"
            if regla_rota == "inversion":
                respuesta = _respaldo(user, "inversion")
            elif regla_rota:
                respuesta = _respaldo(
                    user, "chat", contexto=contexto_financiero(session, user, today, patrones=[])
                )

    session.add(CoachMessage(user_id=user.id, tipo="chat_user", contenido=mensaje, fecha=today))
    del_coach = CoachMessage(user_id=user.id, tipo="chat_coach", contenido=respuesta, fecha=today)
    session.add(del_coach)
    session.commit()
    session.refresh(del_coach)
    return del_coach
