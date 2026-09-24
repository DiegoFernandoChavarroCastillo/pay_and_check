from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.deps import get_current_user
from app.models.user import User
from app.schemas.report import WeeklyReportResponse
from app.services.budget_lookup import get_active_budget_for_user
from app.services.groq_client import GroqServiceError, generate_weekly_recommendations
from app.services.weekly_report import build_weekly_summary, summary_to_text

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", response_model=WeeklyReportResponse)
def weekly_report(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WeeklyReportResponse:
    budget = get_active_budget_for_user(session, current_user.id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay un presupuesto activo.")

    summary = build_weekly_summary(session, current_user.id, budget)

    try:
        recomendaciones = generate_weekly_recommendations(summary_to_text(summary))
    except GroqServiceError:
        # Un fallo de Groq no debe tumbar el resumen numérico, que sigue siendo útil.
        recomendaciones = "No se pudieron generar recomendaciones de IA en este momento."

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
