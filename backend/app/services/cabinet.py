from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.clock import stamp
from app.domain.products import get_product, purposes
from app.domain.scoring import annuity_payment
from app.domain.state_machine import TransitionError, log_event, transition
from app.models import Application, Company, Contract, InfoRequest, ScoreResult, User
from app.services.pipeline import continue_pipeline


def load_application(db: Session, application_id: UUID) -> Application | None:
    current = db.get(Application, application_id)
    if current is not None:
        db.expire(current)
    return db.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.company),
            selectinload(Application.events),
            selectinload(Application.checks),
            selectinload(Application.scores),
            selectinload(Application.info_requests),
            selectinload(Application.contracts),
        )
    )


def owned_or_404(db: Session, application_id: UUID, user: User) -> Application:
    application = load_application(db, application_id)
    if application is None or application.company.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return application


def any_or_404(db: Session, application_id: UUID) -> Application:
    application = load_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return application


def list_for_client(db: Session, user: User) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .join(Company)
            .where(Company.owner_user_id == user.id)
            .options(selectinload(Application.company), selectinload(Application.checks))
            .order_by(Application.created_at.desc())
        ).all()
    )


def list_for_staff(db: Session) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .options(selectinload(Application.company), selectinload(Application.checks))
            .order_by(Application.created_at.desc())
        ).all()
    )


def _next_number(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Application)) or 0
    return f"AK-{10001 + count}"


def create_draft(db: Session, user: User, payload) -> Application:
    if payload.purpose not in purposes():
        raise HTTPException(status_code=400, detail="Неизвестная цель финансирования")
    try:
        get_product(payload.product_code)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Неизвестный продукт") from exc
    company = Company(owner_user_id=user.id, name=user.full_name)
    db.add(company)
    db.flush()
    application = Application(
        public_number=_next_number(db),
        company_id=company.id,
        product_code=payload.product_code,
        purpose=payload.purpose,
        amount=payload.amount,
        term_months=payload.term_months,
        monthly_revenue=None,
        monthly_expenses=None,
        comment="",
        status="DRAFT",
    )
    db.add(application)
    db.flush()
    log_event(
        db,
        application,
        actor_type="CLIENT",
        actor_user_id=user.id,
        message="Черновик заявки создан.",
    )
    db.commit()
    return any_or_404(db, application.id)


def update_draft(db: Session, user: User, application_id: UUID, payload) -> Application:
    application = owned_or_404(db, application_id, user)
    if application.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Менять анкету можно только в черновике")
    data = payload.model_dump(exclude_unset=True)
    company = application.company
    if "inn" in data and data["inn"] is not None:
        company.inn = data["inn"].strip()
    if "legal_form" in data and data["legal_form"] is not None:
        company.legal_form = data["legal_form"]
    if "company_name" in data and data["company_name"]:
        company.name = data["company_name"]
    if "product_code" in data and data["product_code"]:
        try:
            get_product(data["product_code"])
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Неизвестный продукт") from exc
        application.product_code = data["product_code"]
    if "purpose" in data and data["purpose"]:
        if data["purpose"] not in purposes():
            raise HTTPException(status_code=400, detail="Неизвестная цель финансирования")
        application.purpose = data["purpose"]
    for field in ("amount", "term_months", "monthly_revenue", "monthly_expenses", "comment"):
        if field in data and data[field] is not None:
            setattr(application, field, data[field])
    db.commit()
    return any_or_404(db, application.id)


def submit(db: Session, user: User, application_id: UUID) -> Application:
    application = owned_or_404(db, application_id, user)
    try:
        transition(
            db,
            application,
            "SUBMITTED",
            actor_type="CLIENT",
            actor_user_id=user.id,
            message="Вы отправили заявку.",
        )
        continue_pipeline(db, application)
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def answer(db: Session, user: User, application_id: UUID, payload) -> Application:
    application = owned_or_404(db, application_id, user)
    pending = next((item for item in reversed(application.info_requests) if item.answer is None), None)
    if application.status != "NEED_INFO" or pending is None:
        raise HTTPException(status_code=409, detail="Сейчас банк не ждёт уточнение")
    pending.answer = payload.answer.strip()
    from datetime import datetime, timezone

    pending.answered_at = datetime.now(timezone.utc)
    if payload.monthly_revenue is not None:
        application.monthly_revenue = payload.monthly_revenue
    try:
        transition(
            db,
            application,
            "VALIDATING",
            actor_type="CLIENT",
            actor_user_id=user.id,
            message="Вы ответили на уточнение.",
        )
        continue_pipeline(db, application)
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def _latest_score(application: Application) -> ScoreResult:
    if not application.scores:
        raise HTTPException(status_code=409, detail="По заявке ещё нет решения")
    return application.scores[-1]


def accept_offer(db: Session, user: User, application_id: UUID) -> Application:
    application = owned_or_404(db, application_id, user)
    if application.status not in {"APPROVED", "APPROVED_WITH_CHANGES"}:
        raise HTTPException(status_code=409, detail="Оформление сейчас недоступно")
    score = _latest_score(application)
    db.add(
        Contract(
            application_id=application.id,
            status="DRAFT",
            terms_json={
                "product_code": application.product_code,
                "amount": float(score.offered_amount or 0),
                "term_months": score.offered_term_months,
                "rate": float(score.offered_rate or 0),
                "monthly_payment": float(score.monthly_payment or 0),
                "simulated": True,
            },
        )
    )
    try:
        transition(
            db,
            application,
            "CONTRACTING",
            actor_type="CLIENT",
            actor_user_id=user.id,
            message="Вы открыли оформление. Подписание в прототипе смоделировано.",
        )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def decline_offer(db: Session, user: User, application_id: UUID) -> Application:
    application = owned_or_404(db, application_id, user)
    try:
        transition(
            db,
            application,
            "CANCELLED",
            actor_type="CLIENT",
            actor_user_id=user.id,
            message="Вы отказались от предложенных условий.",
        )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def sign(db: Session, user: User, application_id: UUID) -> Application:
    application = owned_or_404(db, application_id, user)
    if application.status != "CONTRACTING" or not application.contracts:
        raise HTTPException(status_code=409, detail="Подписывать пока нечего")
    contract = application.contracts[-1]
    from datetime import datetime, timezone

    contract.status = "SIGNED"
    contract.signed_at = datetime.now(timezone.utc)
    try:
        transition(
            db,
            application,
            "ISSUED",
            actor_type="CLIENT",
            actor_user_id=user.id,
            message="Условия подписаны. Выдача денег смоделирована и не является платежом.",
        )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def confirm(db: Session, user: User, application_id: UUID) -> Application:
    application = any_or_404(db, application_id)
    score = _latest_score(application)
    try:
        if application.status == "DECISION_READY" and score.decision in {
            "APPROVED",
            "APPROVED_WITH_CHANGES",
            "REJECTED",
        }:
            transition(
                db,
                application,
                score.decision,
                actor_type="UNDERWRITER",
                actor_user_id=user.id,
                message="Сотрудник подтвердил решение системы.",
                payload={"score_id": str(score.id)},
            )
            score.awaits_employee = False
        else:
            log_event(
                db,
                application,
                actor_type="UNDERWRITER",
                actor_user_id=user.id,
                message="Сотрудник подтвердил текущее решение.",
            )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def override(db: Session, user: User, application_id: UUID, payload) -> Application:
    application = any_or_404(db, application_id)
    comment = payload.comment.strip()
    if len(comment) < 3:
        raise HTTPException(status_code=400, detail="Комментарий к ручному решению обязателен")
    previous = application.scores[-1] if application.scores else None
    amount = payload.amount
    term = payload.term_months
    rate = payload.rate
    payment = None
    if payload.decision == "APPROVED_WITH_CHANGES":
        if amount is None or term is None or rate is None:
            raise HTTPException(status_code=400, detail="Для других условий нужны сумма, срок и ставка")
        payment = annuity_payment(Decimal(amount), Decimal(rate), term)
    elif payload.decision == "APPROVED":
        amount = amount if amount is not None else application.amount
        term = term if term is not None else application.term_months
        if rate is None:
            rate = get_product(application.product_code).base_rate
        payment = annuity_payment(Decimal(amount), Decimal(rate), term)
    else:
        amount = None
        term = None
        rate = None
    row = ScoreResult(
        application_id=application.id,
        score=previous.score if previous else 0,
        financial_position=previous.financial_position if previous else "AVERAGE",
        debt_service=previous.debt_service if previous else "AVERAGE",
        quality_category=previous.quality_category if previous else "IV",
        stop_factors_json=previous.stop_factors_json if previous else [],
        factors_json=[
            {"code": "manual", "title": "Решение сотрудника", "detail": comment},
        ],
        decision=payload.decision,
        offered_amount=amount,
        offered_term_months=term,
        offered_rate=rate,
        monthly_payment=payment,
        explanation=comment,
        client_explanation=comment,
        awaits_employee=False,
        created_at=stamp(db),
    )
    db.add(row)
    db.flush()
    try:
        transition(
            db,
            application,
            payload.decision,
            actor_type="UNDERWRITER",
            actor_user_id=user.id,
            message=f"Сотрудник изменил решение. {comment}",
            payload={"score_id": str(row.id)},
        )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)


def request_info(db: Session, user: User, application_id: UUID, payload) -> Application:
    application = any_or_404(db, application_id)
    question = payload.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=400, detail="Напишите, что нужно уточнить")
    db.add(InfoRequest(application_id=application.id, question=question, asked_by=user.id, created_at=stamp(db)))
    try:
        if application.status != "NEED_INFO":
            transition(
                db,
                application,
                "NEED_INFO",
                actor_type="UNDERWRITER",
                actor_user_id=user.id,
                message=question,
            )
        else:
            log_event(
                db,
                application,
                actor_type="UNDERWRITER",
                actor_user_id=user.id,
                message=question,
            )
    except TransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return any_or_404(db, application.id)
