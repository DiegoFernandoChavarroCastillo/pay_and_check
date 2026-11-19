"""Semilla de la demo (PS-35): organización ECI con su código de convenio, un usuario por plan y un usuario demo
Premium con un presupuesto a mitad de periodo y una alerta de riesgo activa.

    uv run python -m app.db.seed_demo

Se puede correr las veces que haga falta. Los usuarios se buscan por email; al demo se le borran y reconstruyen
sus datos con fechas relativas a su "hoy", así queda siempre a mitad de periodo aunque la prueba E2E lo haya
cambiado. Los planes no se reinician: se aseguran con las funciones de `app/services/planes.py`, que no hacen
nada si la persona ya está en ese plan, y así el código familiar y los usos del convenio no cambian."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.engine import Engine
from sqlmodel import Session, delete, select

from app.core.security import hash_password
from app.core.time import today_for
from app.db.crear_convenio import crear_convenio
from app.db.seed import seed_default_categories
from app.models.ai_usage import AiUsage
from app.models.budget import Budget
from app.models.category import Category, CategoryLimit
from app.models.coach import CoachMessage, EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Achievement, Challenge, PointEvent
from app.models.goal import Goal, GoalContribution
from app.models.income import Income
from app.models.plan import LicenseCode
from app.models.recurring_expense import RecurringExpense
from app.models.user import User
from app.services.groq_client import MODEL
from app.services.planes import cambiar_plan, canjear, datos_de_familia

PASSWORD = "Demo2026!"
DOMINIO = "demo.payandcheck.com"
ORGANIZACION = "ECI"
CODIGO_CONVENIO = "ECI-2026"
VENCE_CONVENIO = date(2026, 12, 31)
MAX_USOS_CONVENIO = 460


@dataclass(frozen=True)
class UsuarioDemo:
    email: str
    nombre: str
    plan: str  # el que se le asegura; "integrante" = se une a la familia del titular
    solicitudes_ia: int  # llamadas exitosas a Groq en el mes, para que se vea el cupo consumido


USUARIOS = (
    UsuarioDemo(f"demo@{DOMINIO}", "Laura Gómez", "premium", 25),
    UsuarioDemo(f"gratis@{DOMINIO}", "Andrés Rojas", "gratis", 12),
    UsuarioDemo(f"institucional@{DOMINIO}", "Camila Torres", "institucional", 40),
    UsuarioDemo(f"familiar.titular@{DOMINIO}", "Valentina Pérez", "familiar", 60),
    UsuarioDemo(f"familiar.integrante@{DOMINIO}", "Mateo Pérez", "integrante", 35),
)

# (días antes de hoy, monto, categoría, descripción, comercio, source). Gastos de una universitaria en Bogotá.
GASTOS = (
    (14, 18_000, "comida", "Almuerzo corrientazo cerca a la U", "Restaurante La Sazón", "manual"),
    (13, 9_000, "comida", "Tinto y empanadas", "Cafetería de la U", "voz"),
    (12, 32_000, "comida", "Pedido de Rappi un domingo", "Rappi", "texto"),
    (11, 15_000, "otros", "Fotocopias e impresiones", "Papelería El Estudiante", "manual"),
    (10, 38_000, "entretenimiento", "Cine con amigos", "Cine Colombia Andino", "texto"),
    (9, 22_000, "comida", "Mercado pequeño", "D1", "manual"),
    (8, 27_000, "salud", "Droguería: acetaminofén y vitaminas", "Droguería Colsubsidio", "manual"),
    (7, 48_000, "entretenimiento", "Cervezas el viernes", "Bar en Chapinero", "voz"),
    (5, 16_900, "entretenimiento", "Suscripción de Spotify", "Spotify", "manual"),
    (4, 85_000, "otros", "Libro para Cálculo II", "Librería Lerner", "texto"),
    (3, 24_000, "comida", "Hamburguesa después de clase", "El Corral", "texto"),
    (1, 360_000, "servicios", "Mi parte del arriendo compartido", None, "manual"),
)


def borrar_datos_de(session: Session, user_id: int) -> None:
    """Todo lo de la persona menos su cuenta y su plan, en el mismo orden de llaves foráneas que `DELETE /me`
    (`app/routers/auth.py`): los gastos apuntan a presupuestos, categorías y gastos fijos."""
    for modelo in (
        GoalContribution, Goal, Challenge, Achievement, PointEvent, EmotionalCheckin, CoachMessage, CategoryLimit,
        AiUsage,
    ):  # fmt: skip
        session.exec(delete(modelo).where(modelo.user_id == user_id))
    session.exec(delete(Expense).where(Expense.user_id == user_id))
    session.exec(delete(Income).where(Income.user_id == user_id))
    session.exec(delete(RecurringExpense).where(RecurringExpense.user_id == user_id))
    session.exec(delete(Budget).where(Budget.owner_id == user_id))
    session.exec(delete(Category).where(Category.owner_id == user_id))
    session.flush()


def _convenio(session: Session) -> LicenseCode:
    try:
        return crear_convenio(session, ORGANIZACION, CODIGO_CONVENIO, VENCE_CONVENIO, MAX_USOS_CONVENIO)
    except ValueError:
        session.rollback()
        existente = session.exec(select(LicenseCode).where(LicenseCode.codigo == CODIGO_CONVENIO)).first()
        if existente is None:
            raise  # el ValueError era por otra cosa (p. ej. la organización está inactiva)
        return existente


def _usuario(session: Session, datos: UsuarioDemo) -> User:
    user = session.exec(select(User).where(User.email == datos.email)).first()
    if user is None:
        user = User(email=datos.email, nombre=datos.nombre)
    user.hashed_password = hash_password(PASSWORD)  # por si alguien la cambió durante la prueba
    session.add(user)
    session.flush()
    return user


def _uso_ia(session: Session, user: User, solicitudes: int) -> None:
    session.exec(delete(AiUsage).where(AiUsage.user_id == user.id))
    mes = today_for(user).strftime("%Y-%m")
    tareas = ("registro", "reaccion", "consejos", "chat", "reporte")
    for i in range(solicitudes):
        session.add(AiUsage(user_id=user.id, tarea=tareas[i % len(tareas)], modelo=MODEL, mes=mes))


def _datos_del_demo(session: Session, user: User, hoy: date) -> None:
    borrar_datos_de(session, user.id)
    categorias = {c.nombre: c.id for c in session.exec(select(Category).where(Category.owner_id.is_(None)))}

    budget = Budget(
        owner_id=user.id, monto_total=Decimal("1200000"), fecha_inicio=hoy - timedelta(days=14),
        fecha_fin=hoy + timedelta(days=15),
    )  # fmt: skip
    session.add(budget)
    session.flush()

    session.add(
        Income(user_id=user.id, budget_id=budget.id, monto=Decimal("150000"), descripcion="Mesada de la tía",
               fecha=hoy - timedelta(days=6))
    )  # fmt: skip

    # Dos gastos fijos: el plan de datos ya se pagó este periodo; la recarga de TuLlave queda por pagar.
    plan_datos = RecurringExpense(
        user_id=user.id, category_id=categorias["servicios"], monto=Decimal("45000"),
        descripcion="Plan de datos del celular", frecuencia="mensual", dia_mes=(hoy - timedelta(days=2)).day,
        fecha_inicio=hoy - timedelta(days=14),
    )  # fmt: skip
    tullave = RecurringExpense(
        user_id=user.id, category_id=categorias["transporte"], monto=Decimal("30000"),
        descripcion="Recarga TuLlave", frecuencia="semanal", dia_semana=hoy.weekday(), fecha_inicio=hoy,
    )  # fmt: skip
    session.add_all([plan_datos, tullave])
    session.flush()
    session.add(
        Expense(user_id=user.id, budget_id=budget.id, category_id=plan_datos.category_id, monto=plan_datos.monto,
                descripcion=plan_datos.descripcion, recurring_expense_id=plan_datos.id, source="recurrente",
                comercio="Claro", fecha=hoy - timedelta(days=2))
    )  # fmt: skip

    for dias, monto, categoria, descripcion, comercio, source in GASTOS:
        session.add(
            Expense(user_id=user.id, budget_id=budget.id, category_id=categorias[categoria], monto=Decimal(monto),
                    descripcion=descripcion, comercio=comercio, source=source, fecha=hoy - timedelta(days=dias),
                    texto_original=descripcion.lower() if source in ("texto", "voz") else None)
        )  # fmt: skip

    meta = Goal(user_id=user.id, nombre="Portátil para la U", monto_objetivo=Decimal("2500000"),
                fecha_limite=hoy + timedelta(days=180))  # fmt: skip
    session.add(meta)
    session.flush()
    session.add(
        GoalContribution(goal_id=meta.id, user_id=user.id, budget_id=budget.id, monto=Decimal("80000"),
                         fecha=hoy - timedelta(days=5))
    )  # fmt: skip


def sembrar_demo(session: Session) -> list[tuple[str, str, str]]:
    """Siembra la demo y devuelve (email, contraseña, plan) de cada usuario."""
    seed_default_categories(session)
    convenio = _convenio(session)

    usuarios = {datos.email: _usuario(session, datos) for datos in USUARIOS}
    titular = None
    for datos in USUARIOS:
        user = usuarios[datos.email]
        hoy = today_for(user)
        if datos.plan in ("premium", "gratis", "familiar"):
            cambiar_plan(session, user, datos.plan)
            if datos.plan == "familiar":
                titular = user
        elif datos.plan == "institucional":
            canjear(session, user, convenio.codigo, hoy)
        else:
            codigo_familiar, _ = datos_de_familia(session, titular)
            canjear(session, user, codigo_familiar, hoy)
        _uso_ia(session, user, datos.solicitudes_ia)

    demo = usuarios[USUARIOS[0].email]
    _datos_del_demo(session, demo, today_for(demo))
    session.commit()

    codigo_familiar, integrantes = datos_de_familia(session, titular)
    plan_visible = {
        "familiar": f"familiar, titular (código {codigo_familiar}, {integrantes} integrantes)",
        "integrante": f"familiar, integrante (código {codigo_familiar})",
    }
    return [(d.email, PASSWORD, plan_visible.get(d.plan, d.plan)) for d in USUARIOS]


def main(engine: Engine | None = None) -> None:
    if engine is None:
        from app.db.session import engine

    with Session(engine) as session:
        cuentas = sembrar_demo(session)
    print(f"Semilla de la demo lista. Código de convenio: {CODIGO_CONVENIO} ({ORGANIZACION}).")
    print("Cuentas de prueba:")
    for email, password, plan in cuentas:
        print(f"  {email:<40} {password:<12} {plan}")


if __name__ == "__main__":
    main()
