"""Promedio de tokens y latencia por tarea de IA, a partir de `ai_usage` (PS-21).

    uv run python -m app.db.reporte_ia [--desde YYYY-MM] [--hasta YYYY-MM]

Es un script y no un endpoint a propósito: no hay un rol de administrador y los promedios de todos los
usuarios no deben quedar abiertos a cualquier cuenta. Los promedios cuentan solo las llamadas exitosas."""

import argparse
from dataclasses import dataclass

from sqlalchemy import case
from sqlmodel import Session, func, select

from app.models.ai_usage import AiUsage


@dataclass
class ResumenTarea:
    tarea: str
    llamadas: int
    exitosas: int
    tokens_entrada: float | None
    tokens_salida: float | None
    latencia_ms: float | None
    respaldos: int
    bloqueadas: int


def promedios_por_tarea(session: Session, desde: str | None = None, hasta: str | None = None) -> list[ResumenTarea]:
    """`desde` y `hasta` son meses "YYYY-MM", ambos incluidos."""

    def _cuenta(condicion):
        return func.coalesce(func.sum(case((condicion, 1), else_=0)), 0)

    consulta = select(
        AiUsage.tarea,
        func.count(),
        _cuenta(AiUsage.exito),
        func.avg(case((AiUsage.exito, AiUsage.tokens_entrada))),
        func.avg(case((AiUsage.exito, AiUsage.tokens_salida))),
        func.avg(case((AiUsage.exito, AiUsage.latencia_ms))),
        _cuenta(AiUsage.uso_respaldo),
        _cuenta(AiUsage.bloqueado_por != "ninguno"),
    )
    if desde:
        consulta = consulta.where(AiUsage.mes >= desde)
    if hasta:
        consulta = consulta.where(AiUsage.mes <= hasta)

    filas = session.exec(consulta.group_by(AiUsage.tarea).order_by(AiUsage.tarea)).all()
    return [
        ResumenTarea(
            tarea=tarea,
            llamadas=llamadas,
            exitosas=int(exitosas),
            tokens_entrada=None if entrada is None else float(entrada),
            tokens_salida=None if salida is None else float(salida),
            latencia_ms=None if latencia is None else float(latencia),
            respaldos=int(respaldos),
            bloqueadas=int(bloqueadas),
        )
        for tarea, llamadas, exitosas, entrada, salida, latencia, respaldos, bloqueadas in filas
    ]


def _fmt(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:.0f}"


def formatear(resumenes: list[ResumenTarea]) -> str:
    cabecera = (
        f"{'tarea':<10} {'llamadas':>8} {'ok':>5} {'tok in':>7} {'tok out':>8} {'ms':>6} {'respaldo':>9} {'bloq.':>6}"
    )
    filas = [
        f"{r.tarea:<10} {r.llamadas:>8} {r.exitosas:>5} {_fmt(r.tokens_entrada):>7} {_fmt(r.tokens_salida):>8} "
        f"{_fmt(r.latencia_ms):>6} {r.respaldos:>9} {r.bloqueadas:>6}"
        for r in resumenes
    ]
    return "\n".join([cabecera, *filas]) if filas else "Sin llamadas registradas en ese rango."


def main() -> None:
    from app.db.session import engine

    parser = argparse.ArgumentParser(description="Promedio de tokens y latencia por tarea de IA.")
    parser.add_argument("--desde", help="Mes inicial, YYYY-MM")
    parser.add_argument("--hasta", help="Mes final, YYYY-MM")
    args = parser.parse_args()
    with Session(engine) as session:
        print(formatear(promedios_por_tarea(session, args.desde, args.hasta)))


if __name__ == "__main__":
    main()
