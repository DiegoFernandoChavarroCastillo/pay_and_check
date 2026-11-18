"""Registro de cada llamada a Groq (PS-21). `groq_client._chat()` no sabe quién llama, así que quien llama
abre un contexto con `usar(session, user, tarea)` y `_chat()` lo lee. Fuera de un contexto no se registra nada.

La fila se guarda con su propio commit nada más terminar la llamada: si la petición acaba en 422, 502 o 402,
el registro ya está. Nunca lleva el texto de la persona (ver `models/ai_usage.py`)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.core.time import today_for
from app.models.ai_usage import AiUsage
from app.models.user import User

logger = logging.getLogger(__name__)

# Las siete tareas de IA del inventario (planFinal §4.4, CU-IA-01 a CU-IA-07).
TAREAS = ("registro", "recibo", "reaccion", "consejos", "chat", "reporte", "wrapped")


@dataclass
class _Contexto:
    session: Session
    user: User
    user_id: int
    tarea: str
    mes: str
    ultima_id: int | None = None


_actual: ContextVar[_Contexto | None] = ContextVar("ia_uso", default=None)


@contextmanager
def usar(session: Session, user: User, tarea: str) -> Iterator[None]:
    """Las llamadas a Groq dentro del bloque se registran a nombre de `user` y de `tarea`."""
    token = _actual.set(
        _Contexto(session, user, user.id, tarea, mes=today_for(user).strftime("%Y-%m"))
    )
    try:
        yield
    finally:
        _actual.reset(token)


def actual() -> _Contexto | None:
    return _actual.get()


# Solicitudes de IA al mes por persona (planFinal §4.2). Por ahora es una constante; en PS-96 sale del plan.
CUPO_IA_MENSUAL = 300


def cupo_de(user: User) -> int:
    return CUPO_IA_MENSUAL


def _contar(session: Session, user_id: int, mes: str) -> int:
    # Solo las llamadas exitosas: ni las fallidas ni las bloqueadas por cupo gastan solicitudes. Lo servido
    # desde caché (los consejos del día) no llama a Groq, así que tampoco deja fila.
    return session.exec(
        select(func.count())
        .select_from(AiUsage)
        .where(AiUsage.user_id == user_id)
        .where(AiUsage.mes == mes)
        .where(AiUsage.exito)
    ).one()


def usadas_en_el_mes(session: Session, user: User) -> int:
    """Solicitudes de IA del mes en curso del usuario (en su zona horaria). No hay un cron de reinicio: al
    cambiar de mes simplemente se cuenta otro `mes`."""
    return _contar(session, user.id, today_for(user).strftime("%Y-%m"))


def cupo_agotado(contexto: _Contexto) -> bool:
    # La revisión y el registro no son atómicos: dos peticiones simultáneas pueden pasarse del tope por unas
    # pocas llamadas. Es aceptable para un tope de costo; no es un límite de seguridad.
    return _contar(contexto.session, contexto.user_id, contexto.mes) >= cupo_de(contexto.user)


def _guardar(contexto: _Contexto, fila: AiUsage) -> None:
    """Commit propio: el registro no puede perderse ni tumbar la petición."""
    try:
        contexto.session.add(fila)
        contexto.session.commit()
        contexto.ultima_id = fila.id
    except Exception:
        logger.exception("ai_usage: no se pudo registrar la llamada")
        contexto.session.rollback()


def registrar(
    contexto: _Contexto,
    modelo: str,
    *,
    exito: bool,
    latencia_ms: int | None = None,
    tokens_entrada: int | None = None,
    tokens_salida: int | None = None,
    uso_respaldo: bool = False,
    bloqueado_por: str = "ninguno",
) -> None:
    _guardar(
        contexto,
        AiUsage(
            user_id=contexto.user_id,
            tarea=contexto.tarea,
            modelo=modelo,
            tokens_entrada=tokens_entrada,
            tokens_salida=tokens_salida,
            latencia_ms=latencia_ms,
            exito=exito,
            uso_respaldo=uso_respaldo,
            bloqueado_por=bloqueado_por,
            mes=contexto.mes,
        ),
    )


def _marcar(*, respaldo: bool = False, bloqueado_por: str | None = None) -> None:
    """Corrige la última fila del contexto con lo que solo se sabe después de la llamada."""
    contexto = _actual.get()
    if contexto is None or contexto.ultima_id is None:
        return
    try:
        fila = contexto.session.get(AiUsage, contexto.ultima_id)
        cambio = False
        if respaldo and not fila.uso_respaldo:
            fila.uso_respaldo, cambio = True, True
        # El primer motivo manda: un bloqueo por cupo no se reetiqueta.
        if bloqueado_por and fila.bloqueado_por == "ninguno":
            fila.bloqueado_por, cambio = bloqueado_por, True
        if cambio:
            contexto.session.add(fila)
            contexto.session.commit()
    except Exception:
        logger.exception("ai_usage: no se pudo marcar la llamada")
        contexto.session.rollback()


def marcar_respaldo() -> None:
    """La persona recibió un texto de respaldo en lugar de lo que dijo el modelo."""
    _marcar(respaldo=True)


def marcar_bloqueo(motivo: str) -> None:
    """La llamada se hizo pero su resultado se descartó por `motivo` ("alcance" o "inyeccion")."""
    _marcar(bloqueado_por=motivo)
