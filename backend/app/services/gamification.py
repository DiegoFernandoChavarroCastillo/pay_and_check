"""Gamificación verificada con datos reales: puntos, rachas, retos e insignias.

Nada aquí se auto-reporta. Todo se recalcula "al vuelo" a partir de los gastos,
check-ins, metas y retos del usuario (mismo enfoque que
`sync_recurring_expenses`: sin scheduler), y el libro `PointEvent` es
idempotente, así que recalcular nunca duplica puntos.

Los puntos premian consistencia y mejora de ratios, no montos absolutos, para
no castigar a quien tiene un presupuesto pequeño.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, or_, select

from app.models.category import Category
from app.models.coach import EmotionalCheckin
from app.models.expense import Expense
from app.models.gamification import Achievement, Challenge, PointEvent
from app.models.goal import Goal, GoalContribution
from app.models.user import User
from app.services.budget_lookup import find_budget_for_date
from app.services.budget_totals import gasto_entre, ratio_ahorro
from app.services.patterns import detect_patterns, fmt

PUNTOS_REGISTRO_DIA = 5
PUNTOS_CHECKIN = 5
PUNTOS_PRIMER_APORTE = 10
PUNTOS_META_CUMPLIDA = 100
PUNTOS_SEMANA_EN_RITMO = 30
PUNTOS_MEJORA_MENSUAL = 50
HITOS_RACHA = {3: 20, 7: 50, 14: 100, 30: 250}
SEMANAS_A_REVISAR = 8
DURACION_RETO_DIAS = 7

# (puntos mínimos, nombre es, nombre en)
NIVELES = [
    (0, "Aprendiz", "Apprentice"),
    (100, "Organizado", "Organized"),
    (300, "Constante", "Consistent"),
    (700, "Estratega", "Strategist"),
    (1500, "Maestro del presupuesto", "Budget Master"),
    (3000, "Leyenda", "Legend"),
]

# codigo -> idioma -> (nombre, descripción)
INSIGNIAS = {
    "primer_registro": {
        "es": ("Primer paso", "Registraste tu primer gasto."),
        "en": ("First step", "You logged your first expense."),
    },
    "racha_3": {
        "es": ("Racha de 3 días", "Tres días seguidos al tanto de tu dinero."),
        "en": ("3-day streak", "Three days in a row on top of your money."),
    },
    "racha_7": {
        "es": ("Semana perfecta", "Siete días seguidos con registro."),
        "en": ("Perfect week", "Seven days in a row with activity."),
    },
    "racha_30": {
        "es": ("Racha de 30 días", "Un mes entero sin soltar el hábito."),
        "en": ("30-day streak", "A whole month keeping the habit."),
    },
    "primer_checkin": {
        "es": ("Me escucho", "Hiciste tu primer check-in emocional."),
        "en": ("Tuning in", "You did your first emotional check-in."),
    },
    "checkins_7": {
        "es": ("Autoconocimiento", "Siete check-ins emocionales."),
        "en": ("Self-awareness", "Seven emotional check-ins."),
    },
    "primera_meta": {
        "es": ("Con rumbo", "Creaste tu primera meta de ahorro."),
        "en": ("On course", "You created your first savings goal."),
    },
    "meta_cumplida": {
        "es": ("Meta cumplida", "Completaste una meta de ahorro con dinero realmente apartado."),
        "en": ("Goal reached", "You completed a savings goal with money actually set aside."),
    },
    "primer_reto": {
        "es": ("Reto superado", "Cumpliste tu primer reto."),
        "en": ("Challenge beaten", "You completed your first challenge."),
    },
    "retos_3": {
        "es": ("Imparable", "Tres retos cumplidos."),
        "en": ("Unstoppable", "Three challenges completed."),
    },
    "equilibrio": {
        "es": ("Equilibrio", "Cerraste una semana por debajo de tu ritmo de gasto."),
        "en": ("Balance", "You closed a week below your spending pace."),
    },
    "escaner": {
        "es": ("Ojo de escáner", "Registraste un gasto desde la foto de un recibo."),
        "en": ("Scanner eye", "You logged an expense from a receipt photo."),
    },
}

_TEXTOS_RETO = {
    "es": {
        "reducir_categoria": "Gasta máximo {objetivo} en {categoria} en 7 días ({pct}% menos que tu "
        "referencia semanal de {base}).",
        "dias_sin_gasto": "Acumula {n} días sin gastos opcionales en los próximos 7 días.",
        "checkins": "Haz {n} check-ins emocionales en los próximos 7 días.",
        "titulo_reducir_categoria": "{pct}% menos en {categoria}",
        "titulo_dias_sin_gasto": "{n} días sin gasto opcional",
        "titulo_checkins": "{n} check-ins esta semana",
    },
    "en": {
        "reducir_categoria": "Spend at most {objetivo} on {categoria} over 7 days ({pct}% less than your "
        "weekly baseline of {base}).",
        "dias_sin_gasto": "Reach {n} days without optional spending over the next 7 days.",
        "checkins": "Do {n} emotional check-ins over the next 7 days.",
        "titulo_reducir_categoria": "{pct}% less on {categoria}",
        "titulo_dias_sin_gasto": "{n} days without optional spending",
        "titulo_checkins": "{n} check-ins this week",
    },
}

# plantilla -> (puntos, objetivo por defecto)
PLANTILLAS = {"reducir_categoria": (50, None), "dias_sin_gasto": (40, 3), "checkins": (30, 5)}


class ChallengeError(ValueError):
    """El reto no se puede crear con los datos actuales del usuario."""


@dataclass
class SyncResult:
    eventos: list[PointEvent] = field(default_factory=list)
    insignias: list[str] = field(default_factory=list)


def _t(idioma: str, clave: str, **kwargs) -> str:
    return _TEXTOS_RETO.get(idioma, _TEXTOS_RETO["es"])[clave].format(**kwargs)


# --- Actividad y rachas -----------------------------------------------------


def dias_con_gasto(session: Session, user_id: int, today: date) -> set[date]:
    """Días con al menos un gasto registrado por el usuario. Los generados por
    una recurrencia no cuentan: no hubo acción del usuario ese día."""
    return set(
        session.exec(
            select(Expense.fecha)
            .where(Expense.user_id == user_id)
            .where(Expense.source != "recurrente")
            .where(Expense.fecha <= today)
            .distinct()
        ).all()
    )


def dias_con_checkin(session: Session, user_id: int, today: date) -> set[date]:
    return set(
        session.exec(
            select(EmotionalCheckin.fecha)
            .where(EmotionalCheckin.user_id == user_id)
            .where(EmotionalCheckin.fecha <= today)
        ).all()
    )


def rachas(dias: set[date]) -> list[tuple[date, int]]:
    """Corridas de días consecutivos como (primer día, longitud)."""
    resultado: list[tuple[date, int]] = []
    for dia in sorted(dias):
        if resultado and resultado[-1][0] + timedelta(days=resultado[-1][1]) == dia:
            resultado[-1] = (resultado[-1][0], resultado[-1][1] + 1)
        else:
            resultado.append((dia, 1))
    return resultado


def racha_actual(dias: set[date], today: date) -> int:
    """Longitud de la racha vigente. Sigue viva si el último día fue ayer: el
    usuario todavía puede registrar hoy."""
    for inicio, longitud in rachas(dias):
        fin = inicio + timedelta(days=longitud - 1)
        if fin in (today, today - timedelta(days=1)):
            return longitud
    return 0


# --- Retos ------------------------------------------------------------------


def _categorias_opcionales(session: Session, user_id: int) -> list[int]:
    return list(
        session.exec(
            select(Category.id)
            .where(or_(Category.owner_id.is_(None), Category.owner_id == user_id))
            .where(Category.tipo == "opcional")
        ).all()
    )


def crear_reto(
    session: Session,
    user: User,
    plantilla: str,
    today: date,
    category_id: int | None = None,
    porcentaje: int = 20,
) -> Challenge:
    if plantilla not in PLANTILLAS:
        raise ChallengeError("Plantilla de reto desconocida.")
    puntos, objetivo_defecto = PLANTILLAS[plantilla]

    activos = select(Challenge).where(
        Challenge.user_id == user.id, Challenge.estado == "activo", Challenge.tipo == plantilla
    )
    if plantilla == "reducir_categoria":
        activos = activos.where(Challenge.category_id == category_id)
    if session.exec(activos).first() is not None:
        raise ChallengeError("Ya tienes un reto activo de ese tipo.")

    reto = Challenge(
        user_id=user.id,
        tipo=plantilla,
        descripcion="",
        objetivo=Decimal(objetivo_defecto or 0),
        fecha_inicio=today,
        fecha_fin=today + timedelta(days=DURACION_RETO_DIAS - 1),
        puntos=puntos,
    )

    if plantilla == "reducir_categoria":
        categoria = session.get(Category, category_id) if category_id is not None else None
        if categoria is None or (categoria.owner_id is not None and categoria.owner_id != user.id):
            raise ChallengeError("Categoría no encontrada.")
        if not 5 <= porcentaje <= 90:
            raise ChallengeError("El porcentaje debe estar entre 5 y 90.")
        ayer = today - timedelta(days=1)
        base = gasto_entre(session, user.id, today - timedelta(days=DURACION_RETO_DIAS), ayer, category_id)
        if base <= 0:
            # Sin gasto la semana pasada, la referencia es el promedio semanal del último mes.
            base = gasto_entre(session, user.id, today - timedelta(days=28), ayer, category_id) / 4
        if base <= 0:
            raise ChallengeError("No hay gasto reciente en esa categoría con el que comparar.")
        base = base.quantize(Decimal("0.01"))
        reto.category_id = category_id
        reto.linea_base = base
        reto.objetivo = (base * (100 - porcentaje) / 100).quantize(Decimal("0.01"))
        reto.descripcion = _t(
            user.idioma,
            "reducir_categoria",
            objetivo=fmt(reto.objetivo),
            categoria=categoria.nombre,
            pct=porcentaje,
            base=fmt(base),
        )
    else:
        reto.descripcion = _t(user.idioma, plantilla, n=objetivo_defecto)

    session.add(reto)
    session.commit()
    session.refresh(reto)
    return reto


def progreso_reto(session: Session, reto: Challenge, today: date) -> tuple[Decimal, str]:
    """(valor actual, estado) de un reto según los datos reales a `today`."""
    if reto.estado != "activo":
        valor = _valor_reto(session, reto, reto.fecha_fin + timedelta(days=1))
        # Un reto de acumular se cierra al llegar al objetivo: lo que pase
        # después dentro de la ventana ya no cambia su resultado.
        if reto.estado == "cumplido" and reto.tipo != "reducir_categoria":
            valor = min(valor, reto.objetivo)
        return valor, reto.estado

    terminado = today > reto.fecha_fin
    valor = _valor_reto(session, reto, today)

    if reto.tipo == "reducir_categoria":
        # Solo se sabe si se cumplió cuando la ventana termina.
        if not terminado:
            return valor, "activo"
        return valor, "cumplido" if valor <= reto.objetivo else "fallido"

    if valor >= reto.objetivo:
        return valor, "cumplido"
    return valor, "fallido" if terminado else "activo"


def _valor_reto(session: Session, reto: Challenge, today: date) -> Decimal:
    hasta = min(today, reto.fecha_fin)
    if reto.tipo == "reducir_categoria":
        return gasto_entre(session, reto.user_id, reto.fecha_inicio, hasta, reto.category_id)

    if reto.tipo == "checkins":
        return Decimal(
            session.exec(
                select(func.count())
                .select_from(EmotionalCheckin)
                .where(EmotionalCheckin.user_id == reto.user_id)
                .where(EmotionalCheckin.fecha >= reto.fecha_inicio)
                .where(EmotionalCheckin.fecha <= hasta)
            ).one()
        )

    # dias_sin_gasto: solo cuentan días ya terminados (el de hoy aún puede cambiar).
    ultimo_dia_cerrado = min(today - timedelta(days=1), reto.fecha_fin)
    opcionales = _categorias_opcionales(session, reto.user_id)
    dias_con_gasto_opcional = set(
        session.exec(
            select(Expense.fecha)
            .where(Expense.user_id == reto.user_id)
            .where(Expense.category_id.in_(opcionales))
            .where(Expense.fecha >= reto.fecha_inicio)
            .where(Expense.fecha <= ultimo_dia_cerrado)
            .distinct()
        ).all()
    )
    dias_cerrados = max((ultimo_dia_cerrado - reto.fecha_inicio).days + 1, 0)
    return Decimal(dias_cerrados - len(dias_con_gasto_opcional))


def sugerencias_de_retos(session: Session, user: User, today: date) -> list[dict]:
    """Retos que el usuario puede aceptar hoy: los que salen de sus patrones
    de gasto, más los generales. Se omiten los tipos que ya tiene activos."""
    activos = {
        (r.tipo, r.category_id)
        for r in session.exec(
            select(Challenge).where(Challenge.user_id == user.id).where(Challenge.estado == "activo")
        ).all()
    }
    tipos_activos = {tipo for tipo, _ in activos}

    sugerencias: list[dict] = []
    vistos: set[tuple[str, int | None]] = set()
    for patron in detect_patterns(session, user, today):
        accion = patron.accion or {}
        payload = accion.get("payload", {})
        if accion.get("tipo") != "crear_reto" or payload.get("plantilla") != "reducir_categoria":
            continue
        clave = ("reducir_categoria", payload["category_id"])
        if clave in activos or clave in vistos:
            continue
        vistos.add(clave)
        sugerencias.append(
            {
                "plantilla": "reducir_categoria",
                "category_id": payload["category_id"],
                "porcentaje": payload["porcentaje"],
                "titulo": _t(
                    user.idioma,
                    "titulo_reducir_categoria",
                    pct=payload["porcentaje"],
                    categoria=patron.datos.get("categoria", ""),
                ),
                "motivo": patron.descripcion,
                "puntos": PLANTILLAS["reducir_categoria"][0],
            }
        )

    for plantilla in ("dias_sin_gasto", "checkins"):
        if plantilla in tipos_activos:
            continue
        puntos, objetivo = PLANTILLAS[plantilla]
        sugerencias.append(
            {
                "plantilla": plantilla,
                "category_id": None,
                "porcentaje": None,
                "titulo": _t(user.idioma, f"titulo_{plantilla}", n=objetivo),
                "motivo": _t(user.idioma, plantilla, n=objetivo),
                "puntos": puntos,
            }
        )
    return sugerencias


# --- Sincronización ---------------------------------------------------------


def sync_gamification(session: Session, user: User, today: date) -> SyncResult:
    """Otorga los puntos e insignias que correspondan según los datos actuales."""
    try:
        return _sync_gamification(session, user, today)
    except IntegrityError:
        # Otra petición simultánea del mismo usuario (la app pide perfil y retos
        # a la vez) ya otorgó lo mismo y las restricciones únicas frenaron el
        # duplicado. Se descarta este intento: lo otorgado ya quedó guardado.
        session.rollback()
        return SyncResult()


def _sync_gamification(session: Session, user: User, today: date) -> SyncResult:
    resultado = SyncResult()
    claves = set(session.exec(select(PointEvent.clave).where(PointEvent.user_id == user.id)).all())

    def otorgar(clave: str, tipo: str, puntos: int, fecha: date) -> None:
        if clave in claves:
            return
        claves.add(clave)
        evento = PointEvent(user_id=user.id, clave=clave, tipo=tipo, puntos=puntos, fecha=fecha)
        session.add(evento)
        resultado.eventos.append(evento)

    gastos = dias_con_gasto(session, user.id, today)
    checkins = dias_con_checkin(session, user.id, today)
    actividad = gastos | checkins

    for dia in gastos:
        otorgar(f"registro:{dia.isoformat()}", "registro", PUNTOS_REGISTRO_DIA, dia)
    for dia in checkins:
        otorgar(f"checkin:{dia.isoformat()}", "checkin", PUNTOS_CHECKIN, dia)

    todas_las_rachas = rachas(actividad)
    for inicio, longitud in todas_las_rachas:
        for hito, puntos in HITOS_RACHA.items():
            if longitud >= hito:
                otorgar(
                    f"racha:{hito}:{inicio.isoformat()}", "racha", puntos, inicio + timedelta(days=hito - 1)
                )

    retos = session.exec(select(Challenge).where(Challenge.user_id == user.id)).all()
    for reto in retos:
        if reto.estado == "activo":
            _, reto.estado = progreso_reto(session, reto, today)
            session.add(reto)
        if reto.estado == "cumplido":
            otorgar(f"reto:{reto.id}", "reto", reto.puntos, min(today, reto.fecha_fin))

    metas = session.exec(select(Goal).where(Goal.user_id == user.id)).all()
    metas_con_aportes = set(
        session.exec(select(GoalContribution.goal_id).where(GoalContribution.user_id == user.id).distinct()).all()
    )
    for meta in metas:
        if meta.id in metas_con_aportes:
            otorgar(f"primer_aporte:{meta.id}", "aporte", PUNTOS_PRIMER_APORTE, today)
        if meta.estado == "cumplida":
            otorgar(f"meta:{meta.id}", "meta", PUNTOS_META_CUMPLIDA, meta.cumplida_en or today)

    _otorgar_semanas_en_ritmo(session, user, today, actividad, otorgar)
    _otorgar_mejora_mensual(session, user, today, otorgar)

    resultado.insignias = _desbloquear_insignias(
        session, user, gastos, checkins, todas_las_rachas, retos, metas, claves
    )
    session.commit()
    for evento in resultado.eventos:
        session.refresh(evento)
    return resultado


def _otorgar_semanas_en_ritmo(session: Session, user: User, today: date, actividad: set[date], otorgar) -> None:
    lunes_actual = today - timedelta(days=today.weekday())
    for semanas_atras in range(1, SEMANAS_A_REVISAR + 1):
        lunes = lunes_actual - timedelta(days=7 * semanas_atras)
        domingo = lunes + timedelta(days=6)
        budget = find_budget_for_date(session, user.id, lunes)
        # La semana debe caer completa dentro del presupuesto y tener actividad:
        # no se premia "gastar poco" por simplemente no haber usado la app.
        if budget is None or budget.fecha_fin < domingo:
            continue
        if not any(lunes <= dia <= domingo for dia in actividad):
            continue
        semanas_del_periodo = Decimal((budget.fecha_fin - budget.fecha_inicio).days + 1) / 7
        ritmo = budget.monto_total / semanas_del_periodo
        if gasto_entre(session, user.id, lunes, domingo) <= ritmo:
            otorgar(f"semana_en_ritmo:{lunes.isoformat()}", "semana_en_ritmo", PUNTOS_SEMANA_EN_RITMO, domingo)


def _mes_anterior(primer_dia: date) -> tuple[date, date]:
    ultimo = primer_dia - timedelta(days=1)
    return ultimo.replace(day=1), ultimo


def _otorgar_mejora_mensual(session: Session, user: User, today: date, otorgar) -> None:
    inicio_1, fin_1 = _mes_anterior(today.replace(day=1))
    inicio_2, fin_2 = _mes_anterior(inicio_1)
    ratio_1 = ratio_ahorro(session, user.id, inicio_1, fin_1)
    ratio_2 = ratio_ahorro(session, user.id, inicio_2, fin_2)
    if ratio_1 is not None and ratio_2 is not None and ratio_1 > ratio_2:
        otorgar(f"mejora_mensual:{inicio_1:%Y-%m}", "mejora_mensual", PUNTOS_MEJORA_MENSUAL, fin_1)


def _desbloquear_insignias(
    session: Session, user: User, gastos, checkins, todas_las_rachas, retos, metas, claves
) -> list[str]:
    mejor_racha = max((longitud for _, longitud in todas_las_rachas), default=0)
    retos_cumplidos = sum(1 for r in retos if r.estado == "cumplido")
    uso_ocr = session.exec(
        select(Expense.id).where(Expense.user_id == user.id).where(Expense.source == "ocr").limit(1)
    ).first()

    condiciones = {
        "primer_registro": bool(gastos),
        "racha_3": mejor_racha >= 3,
        "racha_7": mejor_racha >= 7,
        "racha_30": mejor_racha >= 30,
        "primer_checkin": bool(checkins),
        "checkins_7": len(checkins) >= 7,
        "primera_meta": bool(metas),
        "meta_cumplida": any(m.estado == "cumplida" for m in metas),
        "primer_reto": retos_cumplidos >= 1,
        "retos_3": retos_cumplidos >= 3,
        "equilibrio": any(clave.startswith("semana_en_ritmo:") for clave in claves),
        "escaner": uso_ocr is not None,
    }

    ya = set(session.exec(select(Achievement.codigo).where(Achievement.user_id == user.id)).all())
    nuevas = [codigo for codigo, cumple in condiciones.items() if cumple and codigo not in ya]
    for codigo in nuevas:
        session.add(Achievement(user_id=user.id, codigo=codigo))
    return nuevas


# --- Perfil -----------------------------------------------------------------


def nivel_para(puntos: int, idioma: str) -> dict:
    indice = max(i for i, (minimo, _, _) in enumerate(NIVELES) if puntos >= minimo)
    minimo, nombre_es, nombre_en = NIVELES[indice]
    siguiente = NIVELES[indice + 1][0] if indice + 1 < len(NIVELES) else None
    return {
        "numero": indice + 1,
        "nombre": nombre_en if idioma == "en" else nombre_es,
        "puntos_nivel": minimo,
        "puntos_siguiente": siguiente,
    }


def insignia_texto(codigo: str, idioma: str) -> tuple[str, str]:
    textos = INSIGNIAS[codigo]
    return textos.get(idioma, textos["es"])


def metricas(session: Session, user: User, today: date, actividad: set[date]) -> dict:
    """Las tres métricas de `mejoras.md`: ratio de ahorro, consistencia y mejora mensual."""
    inicio_mes = today.replace(day=1)
    ratio_actual = ratio_ahorro(session, user.id, inicio_mes, today)
    ratio_previo = ratio_ahorro(session, user.id, *_mes_anterior(inicio_mes))

    dias_ventana = min(30, max((today - user.created_at.date()).days + 1, 1))
    desde = today - timedelta(days=dias_ventana - 1)
    dias_activos = sum(1 for dia in actividad if desde <= dia <= today)

    return {
        "ratio_ahorro": ratio_actual,
        "consistencia": (Decimal(dias_activos) / dias_ventana).quantize(Decimal("0.0001")),
        "mejora_mensual": ratio_actual - ratio_previo
        if ratio_actual is not None and ratio_previo is not None
        else None,
    }
