"""Panel de Bienestar Universitario: solo cifras agregadas, anonimato k ≥ 5 y acceso con el token de la
organización."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from app.db.seed import seed_default_categories
from app.models.budget import Budget
from app.models.coach import EmotionalCheckin
from app.models.expense import Expense
from app.models.plan import Organization, Subscription
from app.models.user import User
from app.services import panel

HOY = date(2026, 11, 18)
TOKEN = "t0k3n-del-panel"


def _universidad(session: Session, nombre="ECI", token=TOKEN) -> Organization:
    org = Organization(nombre=nombre, panel_token=token)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _estudiante(session: Session, org: Organization, i: int, *, ansioso_dias=0, gasto=Decimal("20000")) -> int:
    user = User(email=f"e{org.id}-{i}@eci.edu.co", nombre=f"Estudiante {i}", hashed_password="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(Subscription(user_id=user.id, plan="institucional", organization_id=org.id))
    budget = Budget(owner_id=user.id, monto_total=Decimal("600000"), fecha_inicio=HOY - timedelta(days=10),
                    fecha_fin=HOY + timedelta(days=20))
    session.add(budget)
    session.commit()
    session.refresh(budget)
    session.add(Expense(user_id=user.id, budget_id=budget.id, category_id=1, monto=gasto, descripcion="secreto",
                        fecha=HOY - timedelta(days=1)))
    for d in range(4):
        animo = "ansioso" if d < ansioso_dias else "tranquilo"
        session.add(EmotionalCheckin(user_id=user.id, fecha=HOY - timedelta(days=d), animo=animo))
    session.commit()
    return user.id


def test_con_menos_de_cinco_estudiantes_no_muestra_nada(db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
        org = _universidad(session)
        for i in range(4):
            _estudiante(session, org, i, ansioso_dias=4)
        datos = panel.construir(session, org, HOY)
    assert datos.estudiantes == 4 and not datos.suficiente
    assert datos.pct_estres is None and datos.animo_30d == {} and datos.categorias_30d == []


def test_agrega_sin_exponer_a_nadie(db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
        org = _universidad(session)
        otra = _universidad(session, "Otra U", "otro")
        for i in range(6):
            _estudiante(session, org, i, ansioso_dias=3 if i < 3 else 0)
        for i in range(5):
            _estudiante(session, otra, i, ansioso_dias=4)  # no deben contar en la ECI
        datos = panel.construir(session, org, HOY)

    assert datos.estudiantes == 6 and datos.suficiente
    assert datos.pct_activos == 100
    assert datos.pct_estres == 50  # 3 de 6 con 3+ días de ansiedad
    assert datos.pct_en_riesgo == 0
    assert datos.categorias_30d == [("comida", 100)]
    assert datos.animo_30d["ansioso"] == round(9 * 100 / 24)
    assert datos.tendencia[-1]["gasto_medio"] == 20000


def test_la_pagina_exige_el_token(client, db_engine):
    with Session(db_engine) as session:
        seed_default_categories(session)
        org = _universidad(session, nombre="ECI <script>")
        sin_token = _universidad(session, "Sin panel", None)
        for i in range(5):
            _estudiante(session, org, i)
        org_id, sin_token_id = org.id, sin_token.id

    assert client.get(f"/panel/{org_id}").status_code == 403
    assert client.get(f"/panel/{org_id}?token=malo").status_code == 403
    assert client.get(f"/panel/{sin_token_id}?token=").status_code == 403
    assert client.get("/panel/9999?token=" + TOKEN).status_code == 403

    r = client.get(f"/panel/{org_id}?token={TOKEN}")
    assert r.status_code == 200
    assert "ECI &lt;script&gt;" in r.text  # el nombre va escapado
    assert "secreto" not in r.text and "@eci.edu.co" not in r.text  # nada individual
    assert r.headers["cache-control"] == "no-store"
