"""Crea un código de convenio (y su organización si no existe), para poder canjearlo.

    uv run python -m app.db.crear_convenio --org ECI --codigo ECI-2026 --vence 2026-12-31 --max-usos 460

Es un script y no un endpoint a propósito: no hay un rol de administrador. `--vence` (último día válido) y
`--max-usos` son opcionales; sin ellos el código no vence ni tiene tope de usos."""

import argparse
from datetime import date

from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

from app.models.plan import LicenseCode, Organization


def crear_convenio(
    session: Session, org: str, codigo: str, vence: date | None = None, max_usos: int | None = None
) -> LicenseCode:
    """Lanza ValueError si el código ya existe, si la organización está inactiva o si `max_usos` no es positivo."""
    org, codigo = org.strip(), codigo.strip().upper()
    if not org or not codigo:
        raise ValueError("La organización y el código no pueden estar vacíos.")
    if max_usos is not None and max_usos < 1:
        raise ValueError("--max-usos debe ser mayor que cero.")
    if session.exec(select(LicenseCode).where(LicenseCode.codigo == codigo)).first() is not None:
        raise ValueError(f"El código {codigo} ya existe.")

    organizacion = session.exec(select(Organization).where(func.lower(Organization.nombre) == org.lower())).first()
    if organizacion is None:
        organizacion = Organization(nombre=org)
        session.add(organizacion)
        session.flush()
    elif not organizacion.activa:
        raise ValueError(f"La organización {organizacion.nombre} está inactiva.")

    convenio = LicenseCode(
        codigo=codigo, tipo="convenio", organization_id=organizacion.id, vence_en=vence, max_usos=max_usos
    )
    session.add(convenio)
    session.commit()
    session.refresh(convenio)
    return convenio


def main(argv: list[str] | None = None, engine: Engine | None = None) -> None:
    parser = argparse.ArgumentParser(description="Crea un código de convenio.")
    parser.add_argument("--org", required=True, help="Nombre de la organización (se crea si no existe)")
    parser.add_argument("--codigo", required=True, help="Código que canjearán las personas")
    parser.add_argument("--vence", type=date.fromisoformat, help="Último día válido, YYYY-MM-DD")
    parser.add_argument("--max-usos", type=int, help="Cuántas personas pueden canjearlo")
    args = parser.parse_args(argv)

    if engine is None:
        from app.db.session import engine

    with Session(engine) as session:
        try:
            convenio = crear_convenio(session, args.org, args.codigo, args.vence, args.max_usos)
        except ValueError as exc:
            raise SystemExit(f"Error: {exc}") from exc
        organizacion = session.get(Organization, convenio.organization_id)
        print(
            f"Convenio listo: organización {organizacion.nombre}, código {convenio.codigo}, "
            f"vence {convenio.vence_en or 'nunca'}, máx. usos {convenio.max_usos or 'sin tope'}."
        )


if __name__ == "__main__":
    main()
