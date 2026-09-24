from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.services.recurring_expenses import sync_recurring_expenses


def _crear_usuario_presupuesto_y_categoria(session: Session) -> tuple[User, Budget, Category]:
    user = User(email="x@test.com", hashed_password="h", nombre="X")
    session.add(user)
    session.commit()
    session.refresh(user)

    budget = Budget(
        owner_id=user.id, monto_total=Decimal("1000000"),
        fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 3, 31),
    )
    cat = Category(nombre="transporte", owner_id=None)
    session.add(budget)
    session.add(cat)
    session.commit()
    session.refresh(budget)
    session.refresh(cat)
    return user, budget, cat


def test_sync_genera_semanas_transcurridas_sin_duplicar(db_engine):
    with Session(db_engine) as session:
        user, _budget, cat = _crear_usuario_presupuesto_y_categoria(session)

        recurrente = RecurringExpense(
            user_id=user.id, category_id=cat.id, monto=Decimal("15000"), descripcion="bus",
            dia_semana=0, fecha_inicio=date(2026, 1, 5),  # un lunes
        )
        session.add(recurrente)
        session.commit()
        session.refresh(recurrente)

        # 3 lunes transcurridos: Jan5, Jan12, Jan19
        sync_recurring_expenses(session, user.id, today=date(2026, 1, 20))
        generados = session.exec(
            select(Expense).where(Expense.recurring_expense_id == recurrente.id)
        ).all()
        assert sorted(e.fecha for e in generados) == [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]

        # Repetir con la misma fecha no duplica
        sync_recurring_expenses(session, user.id, today=date(2026, 1, 20))
        generados2 = session.exec(
            select(Expense).where(Expense.recurring_expense_id == recurrente.id)
        ).all()
        assert len(generados2) == 3

        # Una semana más -> una ocurrencia adicional (Jan26)
        sync_recurring_expenses(session, user.id, today=date(2026, 1, 27))
        generados3 = session.exec(
            select(Expense).where(Expense.recurring_expense_id == recurrente.id)
        ).all()
        assert len(generados3) == 4


def test_sync_no_genera_para_recurrente_inactivo(db_engine):
    with Session(db_engine) as session:
        user, _budget, cat = _crear_usuario_presupuesto_y_categoria(session)
        recurrente = RecurringExpense(
            user_id=user.id, category_id=cat.id, monto=Decimal("15000"), descripcion="bus",
            dia_semana=0, fecha_inicio=date(2026, 1, 5), activo=False,
        )
        session.add(recurrente)
        session.commit()

        sync_recurring_expenses(session, user.id, today=date(2026, 2, 1))
        generados = session.exec(
            select(Expense).where(Expense.recurring_expense_id == recurrente.id)
        ).all()
        assert generados == []


def test_crud_recurring_expenses_via_api(client, auth_headers):
    r = client.post("/categories", json={"nombre": "transporte propio"}, headers=auth_headers)
    cat_id = r.json()["id"]

    r = client.post(
        "/recurring-expenses",
        json={"category_id": cat_id, "monto": "15000.00", "descripcion": "bus", "dia_semana": 0},
        headers=auth_headers,
    )
    assert r.status_code == 201
    recurring_id = r.json()["id"]
    assert r.json()["activo"] is True

    r = client.get("/recurring-expenses", headers=auth_headers)
    assert len(r.json()) == 1

    r = client.patch(f"/recurring-expenses/{recurring_id}", json={"activo": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    r = client.delete(f"/recurring-expenses/{recurring_id}", headers=auth_headers)
    assert r.status_code == 204


def test_recurring_expenses_requiere_autenticacion(client):
    assert client.get("/recurring-expenses").status_code == 401


def test_recurring_expenses_categoria_ajena_da_404(client, make_user):
    headers_a, _ = make_user("a@test.com")
    headers_b, _ = make_user("b@test.com")

    r = client.post("/categories", json={"nombre": "privada de a"}, headers=headers_a)
    cat_id = r.json()["id"]

    r = client.post(
        "/recurring-expenses",
        json={"category_id": cat_id, "monto": "1000", "descripcion": "x", "dia_semana": 0},
        headers=headers_b,
    )
    assert r.status_code == 404
