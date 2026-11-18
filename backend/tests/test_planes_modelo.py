"""PS-94: modelo de datos de los planes y borrado de cuenta."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, func, select

from app.models.group import Group
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.user import User


def _usuario(client, make_user, email):
    headers, _ = make_user(email)
    return headers, client.get("/auth/me", headers=headers).json()["id"]


def _filas(db_engine, modelo):
    with Session(db_engine) as session:
        return list(session.exec(select(modelo)).all())


def test_la_cuenta_nueva_no_tiene_suscripcion_y_eso_equivale_a_gratis(client, auth_headers, db_engine):
    # Sin fila no hay nada que migrar: los usuarios que ya existen quedan en Gratis.
    assert _filas(db_engine, Subscription) == []


def test_las_restricciones_del_modelo(db_engine):
    with Session(db_engine) as session:
        session.add(User(email="a@t.com", hashed_password="x", nombre="A"))
        session.add(Organization(nombre="ECI"))
        session.commit()

    def falla(*filas):
        with Session(db_engine) as session, pytest.raises(IntegrityError):
            session.add_all(filas)
            session.commit()

    falla(Subscription(user_id=1, plan="platino"))  # plan inventado
    falla(Organization(nombre="ECI"))  # nombre único
    falla(LicenseCode(codigo="X", tipo="regalo", organization_id=1))  # tipo inventado
    falla(LicenseCode(codigo="X", tipo="convenio"))  # un convenio es de una organización
    falla(LicenseCode(codigo="X", tipo="familiar", organization_id=1))  # una familiar es de un grupo

    with Session(db_engine) as session:
        session.add(Subscription(user_id=1, plan="premium"))
        session.commit()
    falla(Subscription(user_id=1, plan="gratis"))  # una suscripción por persona


def test_borrar_la_cuenta_borra_su_suscripcion_y_deja_el_convenio(client, make_user, db_engine, llaves_foraneas):
    headers, user_id = _usuario(client, make_user, "a@t.com")
    with Session(db_engine) as session:
        eci = Organization(nombre="ECI")
        session.add(eci)
        session.commit()
        codigo = LicenseCode(codigo="ECI-2026", tipo="convenio", organization_id=eci.id, usos=1)
        session.add(codigo)
        session.commit()
        session.add(
            Subscription(user_id=user_id, plan="institucional", organization_id=eci.id, license_code_id=codigo.id)
        )
        session.commit()

    assert client.delete("/auth/me", headers=headers).status_code == 204

    assert _filas(db_engine, Subscription) == []
    # El convenio es de la organización, no de la persona: sigue ahí con su uso contado.
    assert [(o.nombre, c.usos) for o in _filas(db_engine, Organization) for c in _filas(db_engine, LicenseCode)] == [
        ("ECI", 1)
    ]


def _familia(db_engine, titular_id, integrante_id):
    with Session(db_engine) as session:
        grupo = Group(nombre="Familia")
        session.add(grupo)
        session.commit()
        codigo = LicenseCode(codigo="FAM-1", tipo="familiar", group_id=grupo.id)
        session.add(codigo)
        session.commit()
        for user_id, titular in ((titular_id, True), (integrante_id, False)):
            session.get(User, user_id).group_id = grupo.id
            session.add(
                Subscription(
                    user_id=user_id, plan="familiar", es_titular=titular,
                    license_code_id=None if titular else codigo.id,
                )
            )  # fmt: skip
        session.commit()


def test_si_el_titular_borra_su_cuenta_la_familia_se_disuelve(client, make_user, db_engine, llaves_foraneas):
    headers_titular, titular = _usuario(client, make_user, "titular@t.com")
    _, integrante = _usuario(client, make_user, "integrante@t.com")
    _familia(db_engine, titular, integrante)

    assert client.delete("/auth/me", headers=headers_titular).status_code == 204

    with Session(db_engine) as session:
        assert session.get(User, integrante).group_id is None
    # Todos vuelven a Gratis y no queda nada de la familia.
    assert _filas(db_engine, Subscription) == []
    assert _filas(db_engine, Group) == [] and _filas(db_engine, LicenseCode) == []


def test_si_un_integrante_borra_su_cuenta_la_familia_sigue(client, make_user, db_engine, llaves_foraneas):
    _, titular = _usuario(client, make_user, "titular@t.com")
    headers_integrante, integrante = _usuario(client, make_user, "integrante@t.com")
    _familia(db_engine, titular, integrante)

    assert client.delete("/auth/me", headers=headers_integrante).status_code == 204

    with Session(db_engine) as session:
        assert session.get(User, titular).group_id is not None
    assert [s.user_id for s in _filas(db_engine, Subscription)] == [titular]
    assert len(_filas(db_engine, Group)) == 1 and len(_filas(db_engine, LicenseCode)) == 1


def test_borrar_la_cuenta_no_deja_filas_en_ninguna_tabla_con_llave_a_users(
    client, make_user, db_engine, llaves_foraneas
):
    """Recorre todas las tablas: si mañana se agrega una con `user_id` y `delete_me` no la limpia, falla aquí."""
    headers, user_id = _usuario(client, make_user, "a@t.com")
    client.post("/coach/chat", json={"mensaje": "hola"}, headers=headers)  # deja una fila en ai_usage
    with Session(db_engine) as session:
        session.add(Subscription(user_id=user_id, plan="premium"))
        session.commit()

    assert client.delete("/auth/me", headers=headers).status_code == 204

    with Session(db_engine) as session:
        for tabla in SQLModel.metadata.tables.values():
            for columna in tabla.columns:
                if any(fk.target_fullname == "users.id" for fk in columna.foreign_keys):
                    restantes = session.exec(select(func.count()).select_from(tabla).where(columna == user_id)).one()
                    assert restantes == 0, f"{tabla.name}.{columna.name}"
