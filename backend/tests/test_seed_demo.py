from decimal import Decimal

from sqlmodel import Session, func, select

from app.core.time import today_for
from app.db.seed_demo import CODIGO_CONVENIO, USUARIOS, main, sembrar_demo
from app.models.ai_usage import AiUsage
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.goal import Goal, GoalContribution
from app.models.group import Group
from app.models.income import Income
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.services.budget_calculator import calculate_budget_summary
from app.services.planes import plan_de

TABLAS = (
    User, Organization, LicenseCode, Subscription, Group, Category, Budget, Expense, Income, RecurringExpense, Goal,
    GoalContribution, AiUsage,
)  # fmt: skip


def _conteos(session: Session) -> dict[str, int]:
    return {t.__name__: session.exec(select(func.count()).select_from(t)).one() for t in TABLAS}


def _demo(session: Session) -> User:
    return session.exec(select(User).where(User.email == USUARIOS[0].email)).one()


def test_la_semilla_corrida_dos_veces_no_duplica(db_engine, llaves_foraneas):
    with Session(db_engine) as session:
        sembrar_demo(session)
        primera = _conteos(session)
        familia = session.exec(select(LicenseCode).where(LicenseCode.tipo == "familiar")).one().codigo

    with Session(db_engine) as session:
        sembrar_demo(session)
        assert _conteos(session) == primera
        # El código familiar y los usos del convenio no cambian entre corridas.
        assert session.exec(select(LicenseCode).where(LicenseCode.tipo == "familiar")).one().codigo == familia
        convenio = session.exec(select(LicenseCode).where(LicenseCode.codigo == CODIGO_CONVENIO)).one()
        assert convenio.usos == 1

    assert primera["User"] == len(USUARIOS)
    assert primera["Organization"] == 1
    assert primera["Budget"] == 1
    assert primera["RecurringExpense"] == 2
    assert 10 <= primera["Expense"] <= 15
    assert primera["Goal"] == primera["GoalContribution"] == 1


def test_un_usuario_por_plan_y_familia_de_dos(db_engine):
    with Session(db_engine) as session:
        sembrar_demo(session)
        planes = {u.email: plan_de(session, u) for u in session.exec(select(User)).all()}
        titular = session.exec(select(User).where(User.email == USUARIOS[3].email)).one()
        integrantes = session.exec(select(func.count()).select_from(User).where(User.group_id == titular.group_id))

        assert sorted(planes.values()) == ["familiar", "familiar", "gratis", "institucional", "premium"]
        assert planes[USUARIOS[0].email] == "premium"
        assert integrantes.one() == 2


def test_el_demo_queda_a_mitad_de_periodo_y_en_riesgo(db_engine):
    with Session(db_engine) as session:
        sembrar_demo(session)
        demo = _demo(session)
        hoy = today_for(demo)
        budget = session.exec(select(Budget).where(Budget.owner_id == demo.id)).one()
        gastado = sum(e.monto for e in session.exec(select(Expense).where(Expense.user_id == demo.id)))
        ingresos = sum(i.monto for i in session.exec(select(Income).where(Income.user_id == demo.id)))
        aportes = session.exec(select(GoalContribution).where(GoalContribution.user_id == demo.id))
        apartado = sum(c.monto for c in aportes)

        assert budget.fecha_inicio < hoy < budget.fecha_fin
        resumen = calculate_budget_summary(budget, gastado, ingresos, today=hoy, apartado_total=apartado)
        assert resumen.en_riesgo
        assert resumen.disponible_total > Decimal("0")


def test_main_imprime_las_cuentas(db_engine, capsys):
    main(engine=db_engine)
    salida = capsys.readouterr().out
    for datos in USUARIOS:
        assert datos.email in salida
    assert "Demo2026!" in salida
    assert CODIGO_CONVENIO in salida
