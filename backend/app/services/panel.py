"""Panel de Bienestar Universitario: lo que la universidad que paga el plan Institucional ve de sus estudiantes.

Solo cifras agregadas y anónimas. Ningún dato sale de un grupo de menos de `K_ANONIMATO` personas: si un
indicador se calcularía sobre menos, el panel muestra "pocos datos" en su lugar. Nunca hay nombres, correos,
descripciones de gastos ni montos individuales.

Para qué le sirve a la universidad: ver a tiempo el estrés financiero (check-ins de ansiedad, presupuestos que
no alcanzan), que es una de las causas de deserción, y medir si el convenio se usa."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.category import Category
from app.models.coach import EmotionalCheckin
from app.models.expense import Expense
from app.models.goal import Goal
from app.models.plan import Organization, Subscription
from app.models.support import SupportInterest, SupportResource
from app.services.budget_lookup import get_active_budget_for_user
from app.services.budget_totals import summary_for

K_ANONIMATO = 5
SEMANAS_TENDENCIA = 8
ANIMOS = ("ansioso", "preocupado", "neutral", "tranquilo", "confiado")
ANIMOS_DE_ESTRES = ("ansioso", "preocupado")
# Una persona "con señales de estrés" marcó ansiedad o preocupación en al menos estos días de las dos últimas
# semanas.
DIAS_DE_ESTRES = 3


def _pct(parte: int, total: int) -> int | None:
    """Porcentaje entero, o None si el grupo es menor que el umbral de anonimato."""
    if total < K_ANONIMATO:
        return None
    return round(parte * 100 / total)


@dataclass
class Panel:
    organizacion: str
    hoy: date
    estudiantes: int
    activos_semana: int | None = None  # personas con algún registro o check-in en los últimos 7 días
    pct_activos: int | None = None
    pct_en_riesgo: int | None = None  # de quienes tienen presupuesto activo, a cuántos no les alcanza
    pct_con_meta: int | None = None
    pct_estres: int | None = None  # de quienes hicieron check-in en 14 días, cuántos con señales de estrés
    animo_30d: dict[str, int] = field(default_factory=dict)  # % por ánimo
    categorias_30d: list[tuple[str, int]] = field(default_factory=list)  # (categoría, % del gasto)
    # Por semana: gasto medio por estudiante con gastos y % de check-ins con ansiedad o preocupación.
    tendencia: list[dict] = field(default_factory=list)
    # Apoyos de la universidad y cuántos estudiantes se interesaron (None si son menos de K).
    apoyos: list[tuple[str, int | None]] = field(default_factory=list)

    @property
    def suficiente(self) -> bool:
        return self.estudiantes >= K_ANONIMATO


def _miembros(session: Session, org_id: int) -> list[int]:
    return list(
        session.exec(
            select(Subscription.user_id)
            .where(Subscription.organization_id == org_id)
            .where(Subscription.plan == "institucional")
        ).all()
    )


def construir(session: Session, org: Organization, hoy: date) -> Panel:
    ids = _miembros(session, org.id)
    panel = Panel(organizacion=org.nombre, hoy=hoy, estudiantes=len(ids))
    if not panel.suficiente:
        return panel

    # Actividad de la última semana.
    hace_7 = hoy - timedelta(days=6)
    con_gasto = set(
        session.exec(
            select(Expense.user_id).where(Expense.user_id.in_(ids), Expense.fecha >= hace_7, Expense.fecha <= hoy)
        ).all()
    )
    con_checkin = set(
        session.exec(
            select(EmotionalCheckin.user_id).where(
                EmotionalCheckin.user_id.in_(ids), EmotionalCheckin.fecha >= hace_7, EmotionalCheckin.fecha <= hoy
            )
        ).all()
    )
    activos = con_gasto | con_checkin
    panel.activos_semana = len(activos)
    panel.pct_activos = _pct(len(activos), len(ids))

    # Presupuestos que no alcanzan al ritmo actual.
    con_presupuesto = en_riesgo = 0
    for user_id in ids:
        budget = get_active_budget_for_user(session, user_id, hoy)
        if budget is None:
            continue
        con_presupuesto += 1
        en_riesgo += summary_for(session, budget, hoy).en_riesgo
    panel.pct_en_riesgo = _pct(en_riesgo, con_presupuesto)

    con_meta = session.exec(
        select(func.count(func.distinct(Goal.user_id))).where(Goal.user_id.in_(ids), Goal.estado == "activa")
    ).one()
    panel.pct_con_meta = _pct(con_meta, len(ids))

    # Ánimo: distribución de 30 días y señales de estrés en 14 (se leen las semanas de la tendencia de una vez).
    lunes = hoy - timedelta(days=hoy.weekday())
    desde = min(lunes - timedelta(weeks=SEMANAS_TENDENCIA - 1), hoy - timedelta(days=29))
    checkins = session.exec(
        select(EmotionalCheckin.user_id, EmotionalCheckin.animo, EmotionalCheckin.fecha).where(
            EmotionalCheckin.user_id.in_(ids), EmotionalCheckin.fecha >= desde, EmotionalCheckin.fecha <= hoy
        )
    ).all()
    ultimos_30 = [(u, a) for u, a, f in checkins if f >= hoy - timedelta(days=29)]
    if len({u for u, _ in ultimos_30}) >= K_ANONIMATO:
        conteo = Counter(animo for _, animo in ultimos_30)
        total = sum(conteo.values())
        panel.animo_30d = {animo: round(conteo[animo] * 100 / total) for animo in ANIMOS}
    dias_estres: dict[int, int] = defaultdict(int)
    personas_14 = set()
    for user_id, animo, fecha in checkins:
        if fecha >= hoy - timedelta(days=13):
            personas_14.add(user_id)
            dias_estres[user_id] += animo in ANIMOS_DE_ESTRES
    panel.pct_estres = _pct(sum(1 for d in dias_estres.values() if d >= DIAS_DE_ESTRES), len(personas_14))

    # Categorías de 30 días: solo las que usan al menos K personas.
    filas = session.exec(
        select(Category.nombre, Expense.user_id, func.sum(Expense.monto))
        .join(Category, Category.id == Expense.category_id)
        .where(Expense.user_id.in_(ids), Expense.fecha >= hoy - timedelta(days=29), Expense.fecha <= hoy)
        .group_by(Category.nombre, Expense.user_id)
    ).all()
    por_categoria: dict[str, Decimal] = defaultdict(Decimal)
    personas_categoria: dict[str, set[int]] = defaultdict(set)
    for nombre, user_id, total in filas:
        por_categoria[nombre] += Decimal(total)
        personas_categoria[nombre].add(user_id)
    visibles = {n: t for n, t in por_categoria.items() if len(personas_categoria[n]) >= K_ANONIMATO}
    total_visible = sum(visibles.values())
    if total_visible > 0:
        panel.categorias_30d = sorted(
            ((n, round(t * 100 / total_visible)) for n, t in visibles.items()), key=lambda x: -x[1]
        )[:6]

    # Apoyos: cuántos estudiantes tocaron "Me interesa" en cada uno (sin decir quiénes).
    for titulo, interesados in session.exec(
        select(SupportResource.titulo, func.count(SupportInterest.id))
        .join(SupportInterest, SupportInterest.resource_id == SupportResource.id, isouter=True)
        .where(SupportResource.organization_id == org.id)
        .group_by(SupportResource.id, SupportResource.titulo)
        .order_by(func.count(SupportInterest.id).desc())
    ).all():
        panel.apoyos.append((titulo, interesados if interesados >= K_ANONIMATO else None))

    # Tendencia semanal (lunes a domingo), de la más antigua a la actual.
    for i in range(SEMANAS_TENDENCIA - 1, -1, -1):
        inicio = lunes - timedelta(weeks=i)
        fin = inicio + timedelta(days=6)
        gastos = session.exec(
            select(Expense.user_id, func.sum(Expense.monto))
            .where(Expense.user_id.in_(ids), Expense.fecha >= inicio, Expense.fecha <= fin)
            .group_by(Expense.user_id)
        ).all()
        semana_checkins = [(u, a) for u, a, f in checkins if inicio <= f <= fin]
        personas_ck = {u for u, _ in semana_checkins}
        # Parte de los check-ins de la semana con ansiedad o preocupación (no "personas con al menos uno": con
        # varios check-ins por semana casi todos tendrían alguno y la línea no diría nada).
        con_estres = sum(1 for _, a in semana_checkins if a in ANIMOS_DE_ESTRES)
        panel.tendencia.append(
            {
                "semana": inicio.isoformat(),
                "gasto_medio": int(sum(Decimal(t) for _, t in gastos) / len(gastos))
                if len(gastos) >= K_ANONIMATO
                else None,
                "pct_estres": round(con_estres * 100 / len(semana_checkins))
                if len(personas_ck) >= K_ANONIMATO
                else None,
            }
        )
    return panel
