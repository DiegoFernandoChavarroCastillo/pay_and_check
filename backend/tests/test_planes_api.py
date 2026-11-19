"""PS-95: API de planes (listar, consultar, canjear, cambiar) y script de convenios."""

from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.db.crear_convenio import crear_convenio, main
from app.models.group import Group
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.user import User

pytestmark = pytest.mark.usefixtures("llaves_foraneas")  # el orden de los borrados es el de Postgres

HOY = date(2026, 12, 15)
AVISO = "Plan simulado: en el piloto no hay cobro real."


@pytest.fixture(autouse=True)
def _hoy(fijar_hoy):
    fijar_hoy(HOY)


def _persona(make_user, email):
    headers, _ = make_user(email)
    return headers


def _plan(client, headers):
    r = client.get("/me/subscription", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _poner(client, headers, plan):
    return client.put("/me/subscription", json={"plan": plan}, headers=headers)


def _canjear(client, headers, codigo):
    return client.post("/me/subscription/redeem", json={"codigo": codigo}, headers=headers)


def _convenio(db_engine, org="ECI", codigo="ECI-2026", **kwargs):
    with Session(db_engine) as session:
        return crear_convenio(session, org, codigo, **kwargs).id


def _filas(db_engine, modelo):
    with Session(db_engine) as session:
        return list(session.exec(select(modelo)).all())


def _familia(client, make_user):
    """Una familia completa: titular y dos integrantes. Devuelve (headers de cada uno, código familiar)."""
    titular = _persona(make_user, "titular@t.com")
    codigo = _poner(client, titular, "familiar").json()["familia"]["codigo"]
    integrantes = [_persona(make_user, f"integrante{i}@t.com") for i in (1, 2)]
    for headers in integrantes:
        assert _canjear(client, headers, codigo).status_code == 200
    return titular, integrantes, codigo


# --- Consultar ------------------------------------------------------------------


def test_listar_los_planes_con_su_precio_y_cupo(client, auth_headers):
    r = client.get("/plans", headers=auth_headers)
    assert r.status_code == 200
    planes = {p["codigo"]: p for p in r.json()}
    assert {c: (p["precio_cop"], p["cupo_ia_mensual"], p["compartido"]) for c, p in planes.items()} == {
        "gratis": (0, 150, False),
        "institucional": (4998, 300, False),
        "premium": (9990, 300, False),
        "familiar": (19990, 390, True),
    }
    assert planes["familiar"]["max_integrantes"] == 3 and planes["gratis"]["max_integrantes"] is None
    assert client.get("/plans").status_code == 401


def test_la_cuenta_nueva_esta_en_gratis_con_su_cupo_y_fecha_de_reinicio(client, auth_headers):
    assert _plan(client, auth_headers) == {
        "plan": "gratis", "cupo_ia_mensual": 150, "usadas": 0, "restantes": 150, "compartido": False,
        "reinicia_el": "2027-01-01", "organizacion": None, "familia": None, "aviso": None,
    }  # fmt: skip
    assert client.get("/me/subscription").status_code == 401


# --- Cambiar de plan (simulado) --------------------------------------------------


def test_premium_se_activa_y_se_cancela_sin_cobro_real(client, auth_headers, db_engine):
    r = _poner(client, auth_headers, "premium")
    assert r.status_code == 200
    assert (r.json()["plan"], r.json()["cupo_ia_mensual"], r.json()["aviso"]) == ("premium", 300, AVISO)

    assert _poner(client, auth_headers, "premium").status_code == 200  # idempotente
    assert len(_filas(db_engine, Subscription)) == 1

    assert _poner(client, auth_headers, "gratis").json()["plan"] == "gratis"
    assert _filas(db_engine, Subscription) == []


def test_institucional_no_se_pide_se_canjea(client, auth_headers):
    r = _poner(client, auth_headers, "institucional")
    assert r.status_code == 422 and "código de convenio" in r.json()["detail"]
    assert _poner(client, auth_headers, "platino").status_code == 422


def test_el_consumo_del_mes_sale_en_la_suscripcion(client, auth_headers, db_engine):
    from app.models.ai_usage import AiUsage

    with Session(db_engine) as session:
        session.add_all(AiUsage(user_id=1, tarea="chat", modelo="m", mes="2026-12") for _ in range(8))
        session.add(AiUsage(user_id=1, tarea="chat", modelo="m", mes="2026-11"))
        session.commit()

    plan = _plan(client, auth_headers)
    assert (plan["usadas"], plan["restantes"]) == (8, 142)


# --- Convenios ------------------------------------------------------------------


def test_el_codigo_de_convenio_activa_institucional(client, auth_headers, db_engine):
    _convenio(db_engine)

    r = _canjear(client, auth_headers, "  eci-2026 ")  # sin distinguir mayúsculas ni espacios
    assert r.status_code == 200
    assert (r.json()["plan"], r.json()["cupo_ia_mensual"], r.json()["organizacion"], r.json()["aviso"]) == (
        "institucional", 300, "ECI", None,
    )  # fmt: skip

    assert _canjear(client, auth_headers, "ECI-2026").status_code == 200  # canjearlo de nuevo no gasta otro uso
    assert _filas(db_engine, LicenseCode)[0].usos == 1


def test_codigos_invalidos_vencidos_agotados_o_de_un_convenio_inactivo(client, make_user, db_engine, fijar_hoy):
    uno, dos = _persona(make_user, "uno@t.com"), _persona(make_user, "dos@t.com")

    r = _canjear(client, uno, "NO-EXISTE")
    assert r.status_code == 404 and r.json()["detail"] == "Ese código no existe."

    _convenio(db_engine, codigo="VENCE", vence=HOY)
    assert _canjear(client, uno, "VENCE").status_code == 200  # el último día todavía vale
    fijar_hoy(HOY + timedelta(days=1))
    r = _canjear(client, dos, "VENCE")
    assert r.status_code == 422 and r.json()["detail"] == "Ese código venció."

    _convenio(db_engine, codigo="UNO", max_usos=1)
    assert _canjear(client, uno, "UNO").status_code == 200
    r = _canjear(client, dos, "UNO")
    assert r.status_code == 422 and "límite de usos" in r.json()["detail"]
    assert _plan(client, dos)["plan"] == "gratis"

    _convenio(db_engine, org="UTOPIA", codigo="CERRADO")
    with Session(db_engine) as session:
        session.exec(select(Organization).where(Organization.nombre == "UTOPIA")).one().activa = False
        session.commit()
    assert _canjear(client, dos, "CERRADO").status_code == 422


def test_canjear_un_convenio_reemplaza_el_premium(client, auth_headers, db_engine):
    _convenio(db_engine)
    _poner(client, auth_headers, "premium")
    assert _canjear(client, auth_headers, "ECI-2026").json()["plan"] == "institucional"
    assert [s.plan for s in _filas(db_engine, Subscription)] == ["institucional"]


# --- Script de convenios --------------------------------------------------------


def test_el_script_crea_la_organizacion_una_sola_vez(db_engine):
    with Session(db_engine) as session:
        crear_convenio(session, "ECI", "eci-2026", date(2026, 12, 31), 460)
        crear_convenio(session, "eci", "ECI-2027")

    assert len(_filas(db_engine, Organization)) == 1
    primero, segundo = _filas(db_engine, LicenseCode)
    assert primero.organization_id == segundo.organization_id
    assert (primero.codigo, primero.tipo, primero.vence_en, primero.max_usos) == (
        "ECI-2026", "convenio", date(2026, 12, 31), 460,
    )  # fmt: skip
    assert (segundo.vence_en, segundo.max_usos) == (None, None)


def test_el_script_rechaza_lo_que_no_se_puede_crear(db_engine):
    _convenio(db_engine)
    with Session(db_engine) as session:
        for org, codigo, kwargs in (
            ("ECI", "eci-2026", {}),  # ya existe
            ("ECI", "OTRO", {"max_usos": 0}),
            ("", "OTRO", {}),
        ):
            with pytest.raises(ValueError):
                crear_convenio(session, org, codigo, **kwargs)
        session.exec(select(Organization)).one().activa = False
        session.commit()
        with pytest.raises(ValueError, match="inactiva"):
            crear_convenio(session, "ECI", "OTRO")


def test_el_comando_crea_el_convenio_y_se_puede_canjear(client, auth_headers, db_engine, capsys):
    main(["--org", "ECI", "--codigo", "x-1", "--vence", "2026-12-31", "--max-usos", "5"], engine=db_engine)
    salida = capsys.readouterr().out
    assert "organización ECI" in salida and "código X-1" in salida and "2026-12-31" in salida

    assert _canjear(client, auth_headers, "X-1").json()["plan"] == "institucional"

    with pytest.raises(SystemExit, match="ya existe"):
        main(["--org", "ECI", "--codigo", "X-1"], engine=db_engine)
    with pytest.raises(SystemExit) as salio:
        main(["--org", "ECI", "--codigo", "Y", "--vence", "mañana"], engine=db_engine)
    assert salio.value.code == 2


# --- Familia --------------------------------------------------------------------


def test_activar_familiar_crea_la_familia_y_el_codigo_lo_canjean_los_demas(client, make_user, db_engine):
    titular, [uno, dos], codigo = _familia(client, make_user)

    assert codigo.startswith("FAM-")
    mia = _plan(client, titular)
    assert (mia["plan"], mia["cupo_ia_mensual"], mia["compartido"], mia["aviso"]) == ("familiar", 390, True, AVISO)
    assert mia["familia"] == {"codigo": codigo, "integrantes": 3, "max_integrantes": 3, "es_titular": True,
                             "comparte_progreso": False}
    assert _plan(client, uno)["familia"]["es_titular"] is False

    # Pedirlo otra vez no crea otra familia y el código se canjea sin gastar un lugar.
    assert _poner(client, titular, "familiar").json()["familia"]["codigo"] == codigo
    assert _canjear(client, uno, codigo).status_code == 200
    assert len(_filas(db_engine, Group)) == 1 and len(_filas(db_engine, LicenseCode)) == 1

    # Una cuarta persona no cabe.
    cuarta = _persona(make_user, "cuarta@t.com")
    r = _canjear(client, cuarta, codigo)
    assert r.status_code == 422 and "3 integrantes" in r.json()["detail"]
    assert _plan(client, cuarta)["plan"] == "gratis"


def test_un_integrante_no_puede_crear_su_propia_familia(client, make_user):
    _, [integrante, _], _ = _familia(client, make_user)
    r = _poner(client, integrante, "familiar")
    assert r.status_code == 422 and "sal primero" in r.json()["detail"]
    assert _plan(client, integrante)["plan"] == "familiar"


def _volver_a_gratis(client, headers, _):
    assert _poner(client, headers, "gratis").status_code == 200


def _pasar_a_premium(client, headers, _):
    assert _poner(client, headers, "premium").status_code == 200


def _canjear_convenio(client, headers, _):
    assert _canjear(client, headers, "ECI-2026").status_code == 200


def _borrar_cuenta(client, headers, _):
    assert client.delete("/auth/me", headers=headers).status_code == 204


@pytest.mark.parametrize(
    "accion", [_volver_a_gratis, _pasar_a_premium, _canjear_convenio, _borrar_cuenta],
    ids=["vuelve a Gratis", "pasa a Premium", "canjea un convenio", "borra la cuenta"],
)  # fmt: skip
def test_si_el_titular_se_va_la_familia_se_disuelve_y_todos_vuelven_a_gratis(
    client, make_user, db_engine, accion
):
    _convenio(db_engine)
    titular, integrantes, codigo = _familia(client, make_user)

    accion(client, titular, codigo)

    for headers in integrantes:
        assert _plan(client, headers) | {"usadas": 0} == _plan(client, integrantes[0]) | {"usadas": 0}
        assert (_plan(client, headers)["plan"], _plan(client, headers)["familia"]) == ("gratis", None)
    assert _filas(db_engine, Group) == []
    assert _filas(db_engine, LicenseCode)[0].tipo == "convenio" and len(_filas(db_engine, LicenseCode)) == 1
    with Session(db_engine) as session:
        assert all(u.group_id is None for u in session.exec(select(User)).all())
    # El código familiar ya no sirve.
    nuevo = _persona(make_user, "nuevo@t.com")
    assert _canjear(client, nuevo, codigo).status_code == 404


@pytest.mark.parametrize(
    ("accion", "plan"),
    [(_pasar_a_premium, "premium"), (_volver_a_gratis, "gratis"), (_canjear_convenio, "institucional")],
    ids=["pide Premium", "vuelve a Gratis", "canjea un convenio"],
)
def test_si_un_integrante_se_va_sale_de_la_familia_y_los_demas_siguen(
    client, make_user, db_engine, accion, plan
):
    _convenio(db_engine)
    titular, [saliente, otro], codigo = _familia(client, make_user)

    accion(client, saliente, codigo)

    assert _plan(client, saliente)["plan"] == plan and _plan(client, saliente)["familia"] is None
    assert _plan(client, otro)["plan"] == "familiar"
    assert _plan(client, titular)["familia"] == {
        "codigo": codigo, "integrantes": 2, "max_integrantes": 3, "es_titular": True, "comparte_progreso": False,
    }  # fmt: skip
    assert len(_filas(db_engine, Group)) == 1


def test_quien_salio_puede_volver_con_el_mismo_codigo(client, make_user):
    _, [saliente, _], codigo = _familia(client, make_user)
    _poner(client, saliente, "premium")
    assert _canjear(client, saliente, codigo).json()["plan"] == "familiar"


# --- Funciones por plan -----------------------------------------------------------------------------------

def test_los_planes_dicen_que_incluyen(client, auth_headers):
    planes = {p["codigo"]: set(p["funciones"]) for p in client.get("/plans", headers=auth_headers).json()}
    assert "simulador" in planes["gratis"] and "captura_automatica" not in planes["gratis"]
    assert all("captura_automatica" in planes[c] for c in ("premium", "familiar", "institucional"))


def test_la_captura_automatica_es_de_los_planes_pagos(client, auth_headers, categorias, presupuesto):
    from datetime import date, timedelta

    hoy = date.today()
    presupuesto(hoy - timedelta(days=1), hoy + timedelta(days=10))
    gasto = {"monto": "8000", "category_id": 1, "descripcion": "Nequi", "fecha": hoy.isoformat(), "source": "sms"}

    r = client.post("/expenses", json=gasto, headers=auth_headers)
    assert r.status_code == 402
    assert "Premium" in r.json()["detail"]
    # El registro manual sigue libre.
    assert client.post("/expenses", json={**gasto, "source": "manual"}, headers=auth_headers).status_code == 201

    client.put("/me/subscription", json={"plan": "premium"}, headers=auth_headers)
    assert client.post("/expenses", json=gasto, headers=auth_headers).status_code == 201
