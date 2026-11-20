from datetime import date
from decimal import Decimal

from sqlmodel import Session, func, select

from app.db.seed_demo import (
    CODIGO_CONVENIO,
    CODIGO_FAMILIAR,
    DOMINIO,
    EMAIL_DEMO,
    ESTUDIANTES_SINTETICOS,
    main,
    sembrar_demo,
)
from app.models.ai_usage import AiUsage
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.gamification import Achievement
from app.models.goal import Goal, GoalContribution
from app.models.group import Group
from app.models.income import Income
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.recurring_expense import RecurringExpense
from app.models.support import SupportResource
from app.models.user import User
from app.services.budget_calculator import calculate_budget_summary
from app.services.planes import plan_de

HOY = date(2026, 11, 19)

TABLAS = (
    User, Organization, LicenseCode, Subscription, Group, Category, Budget, Expense, Income, RecurringExpense, Goal,
    GoalContribution, AiUsage, SupportResource, Achievement,
)  # fmt: skip


def _conteos(session: Session) -> dict[str, int]:
    return {t.__name__: session.exec(select(func.count()).select_from(t)).one() for t in TABLAS}


def _usuario(session: Session, nombre: str) -> User:
    return session.exec(select(User).where(User.email == f"{nombre}{DOMINIO}")).one()


def test_la_semilla_corrida_dos_veces_no_duplica_ni_cambia_el_panel(db_engine, llaves_foraneas):
    with Session(db_engine) as session:
        _, org = sembrar_demo(session, HOY)
        primera, token = _conteos(session), org.panel_token

    with Session(db_engine) as session:
        _, org = sembrar_demo(session, HOY)
        assert _conteos(session) == primera
        assert org.panel_token == token  # la URL del panel sigue sirviendo
        convenio = session.exec(select(LicenseCode).where(LicenseCode.codigo == CODIGO_CONVENIO)).one()
        assert convenio.usos == 1 + ESTUDIANTES_SINTETICOS  # Valentina y los sintéticos
        assert session.exec(select(LicenseCode).where(LicenseCode.codigo == CODIGO_FAMILIAR)).one()

    assert primera["Organization"] == 1
    assert primera["SupportResource"] == 4
    assert primera["User"] == 5 + ESTUDIANTES_SINTETICOS


def test_una_cuenta_por_plan(db_engine):
    with Session(db_engine) as session:
        sembrar_demo(session, HOY)
        nombres = ("valentina", "laura", "andres", "papa", "camilo")
        planes = {n: plan_de(session, _usuario(session, n)) for n in nombres}
        assert planes == {
            "valentina": "institucional", "laura": "premium", "andres": "gratis", "papa": "familiar",
            "camilo": "familiar",
        }  # fmt: skip
        assert _usuario(session, "papa").group_id == _usuario(session, "camilo").group_id is not None


def test_laura_queda_a_mitad_de_periodo_y_en_riesgo(db_engine):
    with Session(db_engine) as session:
        sembrar_demo(session, HOY)
        laura = _usuario(session, "laura")
        budget = session.exec(select(Budget).where(Budget.owner_id == laura.id)).one()
        gastado = sum(e.monto for e in session.exec(select(Expense).where(Expense.user_id == laura.id)))
        ingresos = sum(i.monto for i in session.exec(select(Income).where(Income.user_id == laura.id)))
        aportes = session.exec(select(GoalContribution).where(GoalContribution.user_id == laura.id))
        apartado = sum(c.monto for c in aportes)

        assert budget.fecha_inicio < HOY < budget.fecha_fin
        fijos = select(func.count()).select_from(RecurringExpense).where(RecurringExpense.user_id == laura.id)
        assert session.exec(fijos).one() == 2
        resumen = calculate_budget_summary(budget, gastado, ingresos, today=HOY, apartado_total=apartado)
        assert resumen.en_riesgo
        assert resumen.disponible_total > Decimal("0")


def test_valentina_ya_tiene_sus_insignias(db_engine):
    """Si la semilla no las otorga, el primer inicio de sesión las anuncia todas juntas."""
    with Session(db_engine) as session:
        sembrar_demo(session, HOY)
        valentina = session.exec(select(User).where(User.email == EMAIL_DEMO)).one()
        insignias = select(func.count()).select_from(Achievement).where(Achievement.user_id == valentina.id)
        assert session.exec(insignias).one() > 5


def test_main_imprime_las_cuentas_y_el_panel(db_engine, capsys):
    main(engine=db_engine)
    salida = capsys.readouterr().out
    for nombre in ("valentina", "laura", "andres", "papa", "camilo"):
        assert f"{nombre}{DOMINIO}" in salida
    assert "Demo2026!" in salida
    assert CODIGO_CONVENIO in salida
    assert "/panel/" in salida
