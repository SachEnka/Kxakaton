from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.clock import stamp
from app.domain.products import get_product
from app.domain.scoring import ScoreInput, evaluate
from app.domain.state_machine import log_event, transition
from app.integrations.egrul_nalog import EgrulLookupError
from app.integrations.registry import resolve_bundle
from app.mocks import MockIntegrationError
from app.models import Application, ExternalCheck, InfoRequest, ScoreResult


def validate_application(application: Application) -> str | None:
    problems: list[str] = []
    company = application.company
    inn = (company.inn or "").strip()
    if not (inn.isdigit() and len(inn) in {10, 12}):
        problems.append("Укажите ИНН: 10 цифр для организации или 12 цифр для ИП.")
    if company.legal_form not in {"OOO", "IP"}:
        problems.append("Укажите форму бизнеса: ООО или ИП.")
    product = get_product(application.product_code)
    if application.amount < product.min_amount:
        problems.append(f"Сумма ниже минимума продукта ({int(product.min_amount)} ₽).")
    if not product.min_term <= application.term_months <= product.max_term:
        problems.append(
            f"Для продукта «{product.title}» срок от {product.min_term} до {product.max_term} месяцев."
        )
    if application.monthly_revenue is None or application.monthly_revenue <= 0:
        problems.append("Укажите среднемесячную выручку в рублях.")
    if not problems:
        return None
    return " ".join(problems)


def _apply_registry(application: Application, egrul: dict) -> None:
    company = application.company
    company.name = egrul.get("short_name") or company.name
    company.ogrn = egrul.get("ogrn")
    company.legal_form = egrul.get("legal_form") or company.legal_form
    company.okved = egrul.get("okved")
    company.director_name = egrul.get("director_name")
    company.address = egrul.get("address")
    company.registry_status = egrul.get("status")
    raw_date = egrul.get("registration_date")
    company.registration_date = date.fromisoformat(raw_date) if raw_date else None


def _save_score(db: Session, application: Application, result) -> ScoreResult:
    row = ScoreResult(
        application_id=application.id,
        score=result.score,
        financial_position=result.financial_position,
        debt_service=result.debt_service,
        quality_category=result.quality_category,
        stop_factors_json=result.stop_factors,
        factors_json=[{"code": item.code, "title": item.title, "detail": item.detail} for item in result.factors],
        decision=result.decision,
        offered_amount=result.offered_amount,
        offered_term_months=result.offered_term_months,
        offered_rate=result.offered_rate,
        monthly_payment=result.monthly_payment,
        explanation=result.explanation,
        client_explanation=result.client_explanation,
        awaits_employee=result.awaits_employee,
        created_at=stamp(db),
    )
    db.add(row)
    db.flush()
    return row


def continue_pipeline(db: Session, application: Application) -> None:
    if application.status == "SUBMITTED":
        transition(
            db,
            application,
            "VALIDATING",
            actor_type="SYSTEM",
            actor_user_id=None,
            message="Мы проверяем, что анкета заполнена.",
        )
    if application.status != "VALIDATING":
        return

    question = validate_application(application)
    if question:
        db.add(InfoRequest(application_id=application.id, question=question, asked_by=None, created_at=stamp(db)))
        transition(
            db,
            application,
            "NEED_INFO",
            actor_type="SYSTEM",
            actor_user_id=None,
            message=question,
        )
        return

    transition(
        db,
        application,
        "ENRICHING",
        actor_type="SYSTEM",
        actor_user_id=None,
        message="Проверяем компанию в ЕГРЮЛ и локальных симуляторах кредитной истории.",
    )
    inn = application.company.inn or ""
    try:
        bundle = resolve_bundle(inn)
    except (MockIntegrationError, EgrulLookupError) as exc:
        db.add(
            ExternalCheck(
                application_id=application.id,
                source="EGRUL",
                status="FAILED",
                request_json={"inn": inn},
                response_json={"error": str(exc)},
                created_at=stamp(db),
            )
        )
        log_event(
            db,
            application,
            actor_type="SYSTEM",
            actor_user_id=None,
            message=str(exc),
        )
        return

    for source, payload in bundle.items():
        db.add(
            ExternalCheck(
                application_id=application.id,
                source=source,
                status="SUCCESS",
                request_json={"inn": inn},
                response_json=payload,
                created_at=stamp(db),
            )
        )
    _apply_registry(application, bundle["EGRUL"])
    transition(
        db,
        application,
        "SCORING",
        actor_type="SYSTEM",
        actor_user_id=None,
        message="Считаем долговую нагрузку и категорию качества.",
    )

    clarified = any(item.answer for item in application.info_requests)
    revenue = application.monthly_revenue
    result = evaluate(
        ScoreInput(
            amount=Decimal(application.amount),
            term_months=application.term_months,
            monthly_revenue=None if revenue is None else Decimal(revenue),
            product_code=application.product_code,
            as_of=date.today(),
            egrul=bundle["EGRUL"],
            bki=bundle["BKI"],
            fns=bundle["FNS"],
            clarified=clarified,
        )
    )
    row = _save_score(db, application, result)
    transition(
        db,
        application,
        "DECISION_READY",
        actor_type="SYSTEM",
        actor_user_id=None,
        message="Предварительное решение готово.",
        payload={"score_id": str(row.id), "category": result.quality_category},
    )

    if result.decision == "NEED_INFO":
        db.add(
            InfoRequest(
                application_id=application.id,
                question=result.info_question or "",
                asked_by=None,
                created_at=stamp(db),
            )
        )
        transition(
            db,
            application,
            "NEED_INFO",
            actor_type="SYSTEM",
            actor_user_id=None,
            message=result.info_question or "Нужны дополнительные сведения.",
        )
        return

    if result.awaits_employee:
        log_event(
            db,
            application,
            actor_type="SYSTEM",
            actor_user_id=None,
            message="Категория IV: решение ждёт сотрудника банка.",
            payload={"score_id": str(row.id)},
        )
        return

    messages = {
        "APPROVED": "Заявку одобрили на рассчитанных условиях.",
        "APPROVED_WITH_CHANGES": "Есть предложение с другими условиями.",
        "REJECTED": result.client_explanation,
    }
    transition(
        db,
        application,
        result.decision,
        actor_type="SYSTEM",
        actor_user_id=None,
        message=messages[result.decision],
        payload={"score_id": str(row.id)},
    )
