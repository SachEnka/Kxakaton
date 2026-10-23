from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import OverrideIn, QuestionIn
from app.security import require_underwriter
from app.services.cabinet import any_or_404, confirm, list_for_staff, override, request_info
from app.services.serialize import application_brief, application_view

router = APIRouter(prefix="/underwriter/applications", tags=["underwriter"])


@router.get("")
def listing(_: User = Depends(require_underwriter), db: Session = Depends(get_db)) -> dict:
    return {"items": [application_brief(item) for item in list_for_staff(db)]}


@router.get("/{application_id}")
def detail(application_id: str, _: User = Depends(require_underwriter), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    return application_view(any_or_404(db, UUID(application_id)), staff=True)


@router.post("/{application_id}/confirm")
def confirm_route(application_id: str, user: User = Depends(require_underwriter), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    return application_view(confirm(db, user, UUID(application_id)), staff=True)


@router.post("/{application_id}/override")
def override_route(
    application_id: str,
    payload: OverrideIn,
    user: User = Depends(require_underwriter),
    db: Session = Depends(get_db),
) -> dict:
    from uuid import UUID

    return application_view(override(db, user, UUID(application_id), payload), staff=True)


@router.post("/{application_id}/request-info")
def request_info_route(
    application_id: str,
    payload: QuestionIn,
    user: User = Depends(require_underwriter),
    db: Session = Depends(get_db),
) -> dict:
    from uuid import UUID

    return application_view(request_info(db, user, UUID(application_id), payload), staff=True)
