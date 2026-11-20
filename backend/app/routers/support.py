from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.time import today_for
from app.db.session import get_session
from app.deps import get_current_user
from app.models.plan import Organization
from app.models.support import SupportInterest, SupportResource
from app.models.user import User
from app.schemas.extras import SupportListResponse, SupportResourceResponse
from app.services import apoyos

router = APIRouter(prefix="/support", tags=["support"])


@router.get("", response_model=SupportListResponse)
def listar_apoyos(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> SupportListResponse:
    """Los apoyos de la universidad del convenio. Sin plan Institucional la lista viene vacía."""
    org_id = apoyos.organizacion_de(session, current_user)
    lista = apoyos.apoyos_de(session, current_user)
    return SupportListResponse(
        organizacion=session.get(Organization, org_id).nombre if org_id else None,
        motivo_sugerencia=apoyos.motivo_para_sugerir(session, current_user, today_for(current_user))
        if lista
        else None,
        apoyos=[
            SupportResourceResponse(
                id=a.recurso.id, tipo=a.recurso.tipo, titulo=a.recurso.titulo, descripcion=a.recurso.descripcion,
                contacto=a.recurso.contacto, me_interesa=a.me_interesa,
            )
            for a in lista
        ],
    )


@router.post("/{resource_id}/interest", status_code=status.HTTP_204_NO_CONTENT)
def me_interesa(
    resource_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> None:
    """Marca el interés (idempotente). La universidad solo ve el total agregado por apoyo."""
    recurso = session.get(SupportResource, resource_id)
    if recurso is None or recurso.organization_id != apoyos.organizacion_de(session, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apoyo no encontrado.")
    existe = session.exec(
        select(SupportInterest).where(
            SupportInterest.user_id == current_user.id, SupportInterest.resource_id == resource_id
        )
    ).first()
    if existe is None:
        session.add(SupportInterest(user_id=current_user.id, resource_id=resource_id))
        session.commit()
