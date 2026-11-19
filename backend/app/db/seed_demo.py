"""Datos de demo para presentar Pay&Check (docs/demo-guion.md). Idempotente: borra y vuelve a crear todo lo suyo.

    uv run python -m app.db.seed_demo            # o, en Docker: docker compose exec api python -m app.db.seed_demo

Crea:
- La universidad "Escuela Colombiana de Ingeniería" con su código de convenio y el token de su panel.
- Valentina, estudiante con plan Institucional y ocho semanas de historia realista: gastos en todas las
  categorías, check-ins, mesada e ingreso de monitoría, arriendo y celular como gastos fijos, la meta "Viaje a
  Santa Marta" con aportes y un reto en curso. Su presupuesto va bien, pero esta semana pesa la comida a domicilio.
- 30 estudiantes sintéticos del mismo convenio para que el panel de Bienestar tenga datos (k ≥ 5), con interés en
  los apoyos de la universidad.
- Los apoyos de la universidad, gastos previstos, una vaca, suscripciones y gastos hormiga de Valentina, y una
  familia de ejemplo (papa@… es el titular y ve el progreso de Camilo).

Solo toca cuentas con correo @demo.payandcheck.app. Al final imprime el usuario, la clave y la URL del panel."""

import random
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.config import POLITICA_VERSION
from app.core.security import hash_password
from app.db.seed import seed_default_categories
from app.db.session import engine
from app.models.budget import Budget
from app.models.category import Category
from app.models.coach import EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Challenge
from app.models.goal import Goal, GoalContribution
from app.models.group import Group
from app.models.income import Income
from app.models.plan import LicenseCode, Organization, Subscription
from app.models.planned_expense import PlannedExpense
from app.models.receivable import Receivable
from app.models.recurring_expense import RecurringExpense
from app.models.support import SupportInterest, SupportResource
from app.models.user import User
from app.routers.auth import delete_me
from app.services.gamification import sync_gamification

DOMINIO = "@demo.payandcheck.app"
EMAIL_DEMO = f"valentina{DOMINIO}"
CLAVE_DEMO = "Demo2026!"
UNIVERSIDAD = "Escuela Colombiana de Ingeniería"
CODIGO_CONVENIO = "ECI-DEMO-2026"
SEMANAS = 8
MESADA = Decimal("1400000")


def _hoy() -> date:
    return datetime.now(UTC).astimezone().date()


def _limpiar(session: Session) -> None:
    for user in session.exec(select(User).where(User.email.like(f"%{DOMINIO}"))).all():
        delete_me(session=session, current_user=user)
    org = session.exec(select(Organization).where(Organization.nombre == UNIVERSIDAD)).first()
    if org is not None:
        for codigo in session.exec(select(LicenseCode).where(LicenseCode.organization_id == org.id)).all():
            session.delete(codigo)
        session.flush()
        for suscripcion in session.exec(select(Subscription).where(Subscription.organization_id == org.id)).all():
            session.delete(suscripcion)
        session.flush()
        for recurso in session.exec(select(SupportResource).where(SupportResource.organization_id == org.id)).all():
            for interes in session.exec(select(SupportInterest).where(SupportInterest.resource_id == recurso.id)).all():
                session.delete(interes)
            session.flush()
            session.delete(recurso)
        session.flush()
        session.delete(org)
    session.commit()


def _persona(
    session: Session, email: str, nombre: str, org: Organization | None, tono: str = "motivador"
) -> User:
    ahora = datetime.now(UTC)
    user = User(
        email=email,
        hashed_password=hash_password(CLAVE_DEMO),
        nombre=nombre,
        coach_tone=tono,
        politica_version=POLITICA_VERSION,
        politica_aceptada_at=ahora,
        sms_consent_at=ahora,
    )
    user.created_at = ahora - timedelta(weeks=SEMANAS, days=3)
    session.add(user)
    session.flush()
    if org is not None:
        session.add(Subscription(user_id=user.id, plan="institucional", organization_id=org.id))
    return user


def _presupuestos(session: Session, user: User, hoy: date, monto: Decimal) -> list[Budget]:
    """Un presupuesto por mes (la mesada), desde el mes en que empieza la historia hasta el actual."""
    inicio = (hoy - timedelta(weeks=SEMANAS)).replace(day=1)
    budgets = []
    while inicio <= hoy:
        siguiente = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        fin = siguiente - timedelta(days=1)
        budget = Budget(owner_id=user.id, monto_total=monto, fecha_inicio=inicio, fecha_fin=fin)
        session.add(budget)
        budgets.append(budget)
        inicio = siguiente
    session.flush()
    return budgets


def _budget_de(budgets: list[Budget], dia: date) -> Budget:
    return next(b for b in budgets if b.fecha_inicio <= dia <= b.fecha_fin)


def _gasto(session, user, budgets, cat, dia, monto, descripcion, source="manual", recurrente=None) -> None:
    session.add(
        Expense(
            user_id=user.id, budget_id=_budget_de(budgets, dia).id, category_id=cat.id, monto=Decimal(monto),
            descripcion=descripcion, source="recurrente" if recurrente else source, fecha=dia,
            recurring_expense_id=recurrente.id if recurrente else None,
        )
    )


def _historia_de_valentina(session: Session, user: User, cats: dict[str, Category], hoy: date) -> None:
    rnd = random.Random(2026)
    budgets = _presupuestos(session, user, hoy, MESADA)
    desde = hoy - timedelta(weeks=SEMANAS)
    animos_semana = ["tranquilo", "confiado", "neutral", "tranquilo", "preocupado", "neutral", "confiado"]

    # Gastos fijos programados: el arriendo y el celular se pagan desde ahí (no cuentan como ritmo diario).
    arriendo = RecurringExpense(user_id=user.id, category_id=cats["vivienda"].id, monto=Decimal("600000"),
                                descripcion="Arriendo", frecuencia="mensual", dia_mes=1, fecha_inicio=desde)
    celular = RecurringExpense(user_id=user.id, category_id=cats["servicios"].id, monto=Decimal("45000"),
                               descripcion="Plan del celular", frecuencia="mensual", dia_mes=15, fecha_inicio=desde)
    session.add_all([arriendo, celular])
    session.flush()

    dia = desde
    while dia <= hoy:
        entre_semana = dia.weekday() < 5
        esta_semana = (hoy - dia).days < hoy.weekday() + 1
        if dia.day == 1:
            _gasto(session, user, budgets, cats["vivienda"], dia, 600000, "Arriendo", recurrente=arriendo)
        if dia.day == 15:
            _gasto(session, user, budgets, cats["servicios"], dia, 45000, "Plan del celular", recurrente=celular)
        if entre_semana:
            _gasto(session, user, budgets, cats["transporte"], dia, 6300, "TransMilenio ida y vuelta",
                   source=rnd.choice(["sms", "manual"]))
            if rnd.random() < 0.8:
                _gasto(session, user, budgets, cats["comida"], dia, rnd.choice([12000, 13500, 15000, 18000]),
                       "Almuerzo cerca de la U", source=rnd.choice(["voz", "texto", "manual"]))
            if rnd.random() < 0.25:
                _gasto(session, user, budgets, cats["estudio"], dia, rnd.choice([3500, 8000, 12000]), "Fotocopias")
        else:
            # Los fines de semana se va más en domicilios, y esta semana más que nunca.
            veces = 2 if esta_semana else 1
            for _ in range(veces):
                if rnd.random() < 0.85:
                    _gasto(session, user, budgets, cats["comida"], dia, rnd.choice([28000, 32000, 38000]),
                           "Domicilio de Rappi", source="sms")
            if rnd.random() < 0.4:
                _gasto(session, user, budgets, cats["entretenimiento"], dia, rnd.choice([16000, 22000]), "Cine")
        if dia.day in (6, 21):
            _gasto(session, user, budgets, cats["compras"], dia, rnd.choice([65000, 89000, 120000]), "Ropa",
                   source="ocr")
        if rnd.random() < 0.85:
            animo = animos_semana[dia.weekday()]
            if esta_semana and dia.weekday() >= 4:
                animo = "preocupado"
            session.add(EmotionalCheckin(user_id=user.id, fecha=dia, animo=animo))
        dia += timedelta(days=1)

    # Ingresos extra: la monitoría.
    for dia_ingreso in (hoy - timedelta(days=40), hoy - timedelta(days=9)):
        if dia_ingreso >= budgets[0].fecha_inicio:
            session.add(Income(user_id=user.id, budget_id=_budget_de(budgets, dia_ingreso).id,
                               monto=Decimal("250000"), descripcion="Monitoría de Cálculo", fecha=dia_ingreso))


    # La meta del viaje, con aportes reales.
    meta = Goal(user_id=user.id, nombre="Viaje a Santa Marta", monto_objetivo=Decimal("2000000"),
                fecha_limite=date(hoy.year + (hoy.month > 3), 3, 31))
    session.add(meta)
    session.flush()
    for semanas_atras, monto in ((6, 100000), (4, 150000), (2, 100000)):
        dia_aporte = hoy - timedelta(weeks=semanas_atras)
        session.add(GoalContribution(goal_id=meta.id, user_id=user.id, budget_id=_budget_de(budgets, dia_aporte).id,
                                     monto=Decimal(monto), fecha=dia_aporte))

    # Suscripciones y gastos hormiga, para que "Gastos que se repiten" tenga qué mostrar.
    for meses_atras in (2, 1, 0):
        dia_cobro = (hoy.replace(day=1) - timedelta(days=28 * meses_atras)).replace(day=8)
        if dia_cobro <= hoy and dia_cobro >= budgets[0].fecha_inicio:
            _gasto(session, user, budgets, cats["entretenimiento"], dia_cobro, 10900, "Spotify", source="sms")
            _gasto(session, user, budgets, cats["entretenimiento"], dia_cobro, 16900, "Netflix", source="sms")
    dia = hoy - timedelta(days=40)
    while dia <= hoy:
        if dia.weekday() < 5 and rnd.random() < 0.7:
            _gasto(session, user, budgets, cats["comida"], dia, 3500, "Tinto y pandebono", source="voz")
        dia += timedelta(days=1)

    # Gastos grandes que vienen.
    navidad = date(hoy.year, 12, 20) if hoy < date(hoy.year, 12, 20) else hoy + timedelta(days=30)
    session.add(PlannedExpense(user_id=user.id, descripcion="Regalos de Navidad", monto=Decimal("180000"),
                               fecha=navidad))
    session.add(PlannedExpense(user_id=user.id, descripcion="Libros y materiales del semestre",
                               monto=Decimal("350000"), fecha=hoy + timedelta(days=62)))

    # Una vaca: la pizza del viernes, pagada por ella para cuatro.
    viernes = hoy - timedelta(days=(hoy.weekday() - 4) % 7 or 7)
    pizza = Expense(user_id=user.id, budget_id=_budget_de(budgets, viernes).id, category_id=cats["comida"].id,
                    monto=Decimal("21000"), descripcion="Pizza con el grupo de Cálculo", source="manual", fecha=viernes)
    session.add(pizza)
    session.flush()
    for persona in ("Juan", "Laura", "Mateo"):
        session.add(Receivable(user_id=user.id, expense_id=pizza.id, persona=persona,
                               descripcion="Pizza con el grupo de Cálculo", monto=Decimal("21000"), fecha=viernes))

    # Un reto en curso.
    lunes = hoy - timedelta(days=hoy.weekday())
    session.add(Challenge(user_id=user.id, tipo="checkins", descripcion="5 check-ins esta semana",
                          objetivo=Decimal("5"), fecha_inicio=lunes, fecha_fin=lunes + timedelta(days=6), puntos=30))


APOYOS = (
    ("alimentacion", "Auxilio de alimentación", "Almuerzo subsidiado en la cafetería central para estudiantes con "
     "dificultades económicas.", "Bienestar Universitario, bloque A, piso 1 · bienestar@escuelaing.edu.co"),
    ("ingresos", "Monitorías pagas", "Cada semestre se abren monitorías en los departamentos; pagan por hora.",
     "Convocatorias en el portal de estudiantes"),
    ("beca", "Beca de permanencia", "Descuento en la matrícula para estudiantes con buen promedio y necesidad "
     "económica demostrada.", "Oficina de Apoyo Financiero"),
    ("bienestar", "Acompañamiento psicológico", "Citas gratuitas y confidenciales con el equipo de psicología.",
     "Agenda en el portal de Bienestar"),
)


def _apoyos(session: Session, org: Organization) -> list[SupportResource]:
    recursos = [
        SupportResource(organization_id=org.id, tipo=tipo, titulo=titulo, descripcion=desc, contacto=contacto)
        for tipo, titulo, desc, contacto in APOYOS
    ]
    session.add_all(recursos)
    session.flush()
    return recursos


def _familia(session: Session, cats: dict[str, Category], hoy: date) -> None:
    """Una familia de ejemplo: el papá paga el plan Familiar y ve el progreso agregado de su hijo, que decidió
    compartirlo."""
    papa = _persona(session, f"papa{DOMINIO}", "Andrés Gómez", None)
    hijo = _persona(session, f"camilo{DOMINIO}", "Camilo Gómez", None)
    grupo = Group(nombre="Familia Gómez")
    session.add(grupo)
    session.flush()
    papa.group_id = hijo.group_id = grupo.id
    session.add_all([papa, hijo])
    session.add(LicenseCode(codigo="FAM-DEMO-2026", tipo="familiar", group_id=grupo.id))
    session.add(Subscription(user_id=papa.id, plan="familiar", es_titular=True))
    session.add(Subscription(user_id=hijo.id, plan="familiar", comparte_progreso=True))
    session.flush()
    rnd = random.Random(7)
    budgets = _presupuestos(session, hijo, hoy, Decimal("900000"))
    dia = hoy - timedelta(weeks=4)
    while dia <= hoy:
        if rnd.random() < 0.75:
            _gasto(session, hijo, budgets, cats["comida"], dia, rnd.choice([9000, 12000, 15000]), "Almuerzo")
            session.add(EmotionalCheckin(user_id=hijo.id, fecha=dia, animo=rnd.choice(["tranquilo", "confiado"])))
        dia += timedelta(days=1)
    meta = Goal(user_id=hijo.id, nombre="Portátil", monto_objetivo=Decimal("2400000"))
    session.add(meta)
    session.flush()
    session.add(GoalContribution(goal_id=meta.id, user_id=hijo.id, budget_id=budgets[-1].id,
                                 monto=Decimal("300000"), fecha=hoy))


def _estudiante_sintetico(session: Session, i: int, org: Organization, cats: dict[str, Category], hoy: date) -> None:
    rnd = random.Random(i)
    user = _persona(session, f"estudiante{i:02d}{DOMINIO}", f"Estudiante {i:02d}", org)
    mesada = Decimal(rnd.choice([900000, 1100000, 1300000, 1600000]))
    budgets = _presupuestos(session, user, hoy, mesada)
    estresado = rnd.random() < 0.3  # cerca de un tercio pasa una mala racha
    gasta_mas = 1.6 if estresado else 1.0
    activo_hasta = hoy if rnd.random() < 0.8 else hoy - timedelta(days=rnd.randint(8, 20))
    dia = hoy - timedelta(weeks=SEMANAS)
    while dia <= activo_hasta:
        if rnd.random() < 0.7:
            cat = rnd.choices(
                ["comida", "transporte", "entretenimiento", "compras", "estudio", "otros"], [45, 25, 10, 8, 7, 5]
            )[0]
            monto = int(rnd.choice([6000, 12000, 15000, 25000, 40000]) * gasta_mas)
            _gasto(session, user, budgets, cats[cat], dia, monto, "Gasto")
        if rnd.random() < 0.6:
            reciente = (hoy - dia).days < 14
            if estresado and reciente:
                animo = rnd.choice(["ansioso", "preocupado", "preocupado", "neutral"])
            else:
                animo = rnd.choice(["tranquilo", "confiado", "neutral", "tranquilo", "preocupado"])
            session.add(EmotionalCheckin(user_id=user.id, fecha=dia, animo=animo))
        dia += timedelta(days=1)
    if rnd.random() < 0.45:
        session.add(Goal(user_id=user.id, nombre="Meta", monto_objetivo=Decimal("800000")))
    # Quien está pasando una mala racha a veces pide apoyo; el resto, de vez en cuando, mira las monitorías.
    recursos = session.exec(select(SupportResource).where(SupportResource.organization_id == org.id)).all()
    for recurso in recursos:
        probabilidad = 0.6 if estresado and recurso.tipo in ("alimentacion", "bienestar", "beca") else 0.15
        if rnd.random() < probabilidad:
            session.add(SupportInterest(user_id=user.id, resource_id=recurso.id))


def main() -> None:
    hoy = _hoy()
    with Session(engine) as session:
        seed_default_categories(session)
        _limpiar(session)
        cats = {c.nombre: c for c in session.exec(select(Category).where(Category.owner_id.is_(None))).all()}

        org = Organization(nombre=UNIVERSIDAD, panel_token=secrets.token_urlsafe(18))
        session.add(org)
        session.flush()
        session.add(LicenseCode(codigo=CODIGO_CONVENIO, tipo="convenio", organization_id=org.id))
        _apoyos(session, org)

        valentina = _persona(session, EMAIL_DEMO, "Valentina Rojas", org, tono="motivador")
        _historia_de_valentina(session, valentina, cats, hoy)
        for i in range(1, 31):
            _estudiante_sintetico(session, i, org, cats, hoy)
        _familia(session, cats, hoy)
        session.commit()
        # Las insignias de la historia ya se ganaron: así el primer inicio de sesión no las anuncia todas juntas.
        for persona in session.exec(select(User).where(User.email.endswith(DOMINIO))).all():
            sync_gamification(session, persona, hoy)
        session.commit()

        print("Demo lista.")
        print(f"  Cuenta:   {EMAIL_DEMO} / {CLAVE_DEMO}")
        print(f"  Convenio: {CODIGO_CONVENIO} (Institucional)")
        print(f"  Familia:  papa{DOMINIO} / {CLAVE_DEMO} (titular; ve el progreso de Camilo)")
        print(f"  Panel:    /panel/{org.id}?token={org.panel_token}")


if __name__ == "__main__":
    main()
