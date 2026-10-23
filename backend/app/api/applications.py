from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.products import products, recommend
from app.models import User
from app.schemas import AnswerIn, DraftIn, DraftPatch, RecommendIn
from app.security import require_client
from app.services.cabinet import (
    accept_offer,
    answer,
    create_draft,
    decline_offer,
    list_for_client,
    owned_or_404,
    sign,
    submit,
    update_draft,
)
from app.services.serialize import application_brief, application_view

router = APIRouter(prefix="/applications", tags=["applications"])


def _card(card) -> dict:
    product = card.product
    return {
        "code": product.code,
        "title": product.title,
        "summary": product.summary,
        "min_amount": float(product.min_amount),
        "max_amount": float(product.max_amount),
        "min_term": product.min_term,
        "max_term": product.max_term,
        "base_rate": float(product.base_rate),
        "fits": card.fits,
        "suggested_amount": float(card.suggested_amount),
        "suggested_term": card.suggested_term,
        "reason": card.reason,
        "recommended": card.recommended,
    }


@router.post("/recommend")
def recommend_product(payload: RecommendIn, _: User = Depends(require_client)) -> dict:
    primary, alternative = recommend(payload.purpose, Decimal(payload.amount), payload.term_months)
    return {"primary": _card(primary), "alternative": None if alternative is None else _card(alternative)}


@router.get("/products")
def list_products(_: User = Depends(require_client)) -> dict:
    return {
        "products": [
            {
                "code": item.code,
                "title": item.title,
                "summary": item.summary,
                "min_amount": float(item.min_amount),
                "max_amount": float(item.max_amount),
                "min_term": item.min_term,
                "max_term": item.max_term,
                "base_rate": float(item.base_rate),
            }
            for item in products().values()
        ]
    }


@router.post("")
def create(payload: DraftIn, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    application = create_draft(db, user, payload)
    return application_view(application, staff=False)


@router.get("")
def listing(user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    rows = list_for_client(db, user)
    return {"items": [application_brief(item) for item in rows]}


@router.get("/{application_id}")
def detail(application_id: str, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = owned_or_404(db, UUID(application_id), user)
    return application_view(application, staff=False)


@router.patch("/{application_id}")
def patch(application_id: str, payload: DraftPatch, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = update_draft(db, user, UUID(application_id), payload)
    return application_view(application, staff=False)


@router.post("/{application_id}/submit")
def submit_route(application_id: str, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = submit(db, user, UUID(application_id))
    return application_view(application, staff=False)


@router.post("/{application_id}/answers")
def answers(application_id: str, payload: AnswerIn, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = answer(db, user, UUID(application_id), payload)
    return application_view(application, staff=False)


@router.post("/{application_id}/accept-offer")
def accept(application_id: str, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = accept_offer(db, user, UUID(application_id))
    return application_view(application, staff=False)


@router.post("/{application_id}/decline-offer")
def decline(application_id: str, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = decline_offer(db, user, UUID(application_id))
    return application_view(application, staff=False)


@router.post("/{application_id}/sign")
def sign_route(application_id: str, user: User = Depends(require_client), db: Session = Depends(get_db)) -> dict:
    from uuid import UUID

    application = sign(db, user, UUID(application_id))
    return application_view(application, staff=False)
