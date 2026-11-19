import re
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.rate_limit import limite_ia
from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.user import User
from app.schemas.report import MonthlyWrappedResponse, TrendsResponse, WeeklyReportResponse
from app.services import ia_uso
from app.services.budget_lookup import get_active_budget_for_user
from app.services.coach import inventa_cifras, rompe_guardrails
from app.services.groq_client import CupoIAAgotado, GroqServiceError, generate_weekly_recommendations
from app.services.trends import build_trends
from app.services.weekly_report import build_weekly_summary, resumen_de_respaldo, summary_to_text
from app.services.wrapped import build_wrapped

_MENCIONA_INVERSION = re.compile(r"invers|invert|invest", re.IGNORECASE)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", response_model=WeeklyReportResponse, dependencies=[Depends(limite_ia)])
def weekly_report(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WeeklyReportResponse:
    today = today_for(current_user)
    budget = get_active_budget_for_user(session, current_user.id, today)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")

    summary = build_weekly_summary(session, current_user.id, budget, today)

    resumen = summary_to_text(summary)
    with ia_uso.usar(session, current_user, "reporte"):
        try:
            recomendaciones = generate_weekly_recommendations(resumen)
        except CupoIAAgotado:
            # Sin cupo el resumen numérico sigue y las recomendaciones son las deterministas.
            recomendaciones = resumen_de_respaldo(summary)
            ia_uso.marcar_respaldo()
        except GroqServiceError:
            # Un fallo de Groq no debe tumbar el resumen numérico, que sigue siendo útil.
            recomendaciones = "No se pudieron generar recomendaciones de IA en este momento."
            ia_uso.marcar_respaldo()
        else:
            # Mismas reglas que el resto del coach: sin culpa, sin inversiones y sin cifras inventadas.
            if (
                not recomendaciones
                or rompe_guardrails(recomendaciones)
                or _MENCIONA_INVERSION.search(recomendaciones)
                or inventa_cifras(recomendaciones, resumen)
            ):
                recomendaciones = resumen_de_respaldo(summary)
                ia_uso.marcar_respaldo()

    return WeeklyReportResponse(
        semana_inicio=summary.semana_inicio,
        semana_fin=summary.semana_fin,
        gasto_total_semana=summary.gasto_total_semana,
        gasto_por_categoria=[
            {"categoria": c.categoria, "monto": c.monto} for c in summary.gasto_por_categoria
        ],
        ritmo_esperado_semanal=summary.ritmo_esperado_semanal,
        diferencia_vs_ritmo=summary.diferencia_vs_ritmo,
        recomendaciones=recomendaciones,
    )


@router.get("/trends", response_model=TrendsResponse)
def trends(
    semanas: int = Query(default=8, ge=2, le=26),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TrendsResponse:
    """Gasto por semana y por categoría para las gráficas. Sin IA: responde rápido."""
    datos = build_trends(session, current_user.id, today_for(current_user), semanas)
    return TrendsResponse.model_validate(asdict(datos))


@router.get("/monthly-wrapped", response_model=MonthlyWrappedResponse, dependencies=[Depends(limite_ia)])
def monthly_wrapped(
    mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resumen del mes indicado (por defecto, el mes en curso del usuario)."""
    today = today_for(current_user)
    if mes is None:
        anio, numero = today.year, today.month
    else:
        anio, numero = (int(parte) for parte in mes.split("-"))
    return build_wrapped(session, current_user, anio, numero, today)
