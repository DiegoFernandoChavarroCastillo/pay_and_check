"""Panel web de Bienestar Universitario (`GET /panel/{org_id}?token=…`): cifras agregadas y anónimas de los
estudiantes del convenio. Es una página HTML para abrir en el navegador; la lógica vive en `services/panel.py`."""

import html
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.db.session import get_session
from app.models.plan import Organization
from app.services import panel as panel_service

router = APIRouter(tags=["panel"])

_PLANTILLA = Template((Path(__file__).parent.parent / "templates" / "panel.html").read_text(encoding="utf-8"))
# El convenio piloto es con una universidad de Bogotá.
ZONA_PANEL = ZoneInfo("America/Bogota")


@router.get("/panel/{org_id}", response_class=HTMLResponse, include_in_schema=False)
def ver_panel(org_id: int, token: str = "", session: Session = Depends(get_session)) -> HTMLResponse:
    org = session.get(Organization, org_id)
    # Mismo error para "no existe" y "token malo": no se revela qué organizaciones hay.
    if org is None or not org.panel_token or not secrets.compare_digest(token, org.panel_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Panel no disponible.")
    hoy = datetime.now(UTC).astimezone(ZONA_PANEL).date()
    datos = panel_service.construir(session, org, hoy)
    carga = {
        "estudiantes": datos.estudiantes,
        "suficiente": datos.suficiente,
        "k": panel_service.K_ANONIMATO,
        "activos_semana": datos.activos_semana,
        "pct_activos": datos.pct_activos,
        "pct_en_riesgo": datos.pct_en_riesgo,
        "pct_con_meta": datos.pct_con_meta,
        "pct_estres": datos.pct_estres,
        "animo": datos.animo_30d,
        "categorias": datos.categorias_30d,
        "tendencia": datos.tendencia,
        "apoyos": datos.apoyos,
    }
    # `</` dentro del JSON cerraría el <script>: se escapa.
    json_seguro = json.dumps(carga, ensure_ascii=False).replace("</", "<\\/")
    pagina = _PLANTILLA.substitute(
        organizacion=html.escape(datos.organizacion),
        fecha=hoy.strftime("%d/%m/%Y"),
        datos=json_seguro,
    )
    return HTMLResponse(pagina, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
