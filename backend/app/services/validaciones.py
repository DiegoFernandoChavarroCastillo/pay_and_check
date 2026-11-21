"""Validaciones de negocio compartidas por varios routers."""

from datetime import date

from fastapi import HTTPException, status

from app.core.time import today_for
from app.models.user import User

FECHA_FUTURA = "La fecha no puede ser posterior a hoy: registra el movimiento cuando ocurra."


def validar_fecha_no_futura(fecha: date, user: User) -> None:
    """Un gasto o ingreso con fecha futura ya contaba en el disponible de hoy: un ingreso que aún no llegó
    inflaba lo que la persona "puede gastar". Lo que viene se anota en Gastos que vienen o en Gastos fijos."""
    if fecha > today_for(user):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, FECHA_FUTURA)
