from decimal import Decimal

from app.domain.products import get_product, purposes

STATUS_LABELS = {
    "DRAFT": "Черновик",
    "SUBMITTED": "Заявка отправлена",
    "VALIDATING": "Проверяем данные",
    "NEED_INFO": "Нужны уточнения",
    "ENRICHING": "Проверяем сведения о компании",
    "SCORING": "Оцениваем заявку",
    "DECISION_READY": "Готовим решение",
    "APPROVED": "Одобрено",
    "APPROVED_WITH_CHANGES": "Есть предложение с другими условиями",
    "REJECTED": "Отказано",
    "CONTRACTING": "Оформление",
    "ISSUED": "Финансирование оформлено",
    "CANCELLED": "Заявка отменена",
}

STAGES = {
    "DRAFT": (
        "Анкета сохранена как черновик.",
        "Заявка ещё не в работе у банка.",
        "Дальше действуете вы: проверьте данные и отправьте заявку.",
    ),
    "SUBMITTED": (
        "Заявка отправлена в банк.",
        "Передаём её на проверку заполнения.",
        "Дальше действует банк.",
    ),
    "VALIDATING": (
        "Заявка принята.",
        "Проверяем, хватает ли сведений для оценки.",
        "Дальше действует банк.",
    ),
    "NEED_INFO": (
        "Проверка остановилась на нехватке сведений.",
        "Без ответа заявка не продолжится.",
        "Дальше действуете вы: ответьте на вопрос ниже.",
    ),
    "ENRICHING": (
        "Анкета прошла проверку заполнения.",
        "Собираем сведения о компании из симуляторов реестров и кредитной истории.",
        "Дальше действует банк.",
    ),
    "SCORING": (
        "Сведения о компании получены.",
        "Считаем нагрузку и категорию качества.",
        "Дальше действует банк.",
    ),
    "DECISION_READY": (
        "Проверки и оценка уже выполнены.",
        "Сотрудник банка смотрит подготовленное решение.",
        "Дальше действует банк.",
    ),
    "APPROVED": (
        "Проверки завершены, запрошенные условия одобрены.",
        "Можно открыть индивидуальные условия.",
        "Дальше действуете вы: перейдите к оформлению и подпишите.",
    ),
    "APPROVED_WITH_CHANGES": (
        "Оценка завершена, запрошенные условия целиком не проходят.",
        "Банк предлагает другие сумму, срок или ставку.",
        "Дальше действуете вы: примите условия или откажитесь.",
    ),
    "REJECTED": (
        "Проверки и оценка завершены.",
        "Кредит на этих данных не выдаётся.",
        "Действий по этой заявке больше нет. Позже можно подать новую.",
    ),
    "CONTRACTING": (
        "Условия согласованы.",
        "На экране индивидуальные условия. Подписание смоделировано.",
        "Дальше действуете вы: нажмите «Подписать».",
    ),
    "ISSUED": (
        "Условия подписаны.",
        "Финансирование в прототипе отмечено как оформленное. Деньги не переводятся.",
        "Заявка завершена.",
    ),
    "CANCELLED": (
        "Вы отказались от предложенных условий.",
        "Заявка закрыта.",
        "Заявка завершена.",
    ),
}

TIMELINE = [
    ("apply", "Заявка", {"DRAFT", "SUBMITTED"}),
    ("check", "Проверка", {"VALIDATING", "NEED_INFO"}),
    ("company", "Компания", {"ENRICHING"}),
    ("score", "Оценка", {"SCORING", "DECISION_READY"}),
    ("decision", "Решение", {"APPROVED", "APPROVED_WITH_CHANGES", "REJECTED", "CANCELLED"}),
    ("deal", "Оформление", {"CONTRACTING", "ISSUED"}),
]

POSITION_LABEL = {"GOOD": "Хорошее", "AVERAGE": "Среднее", "POOR": "Плохое"}
SERVICE_LABEL = {"GOOD": "Хорошее", "AVERAGE": "Среднее", "POOR": "Плохое"}


def _num(value) -> float | None:
    if value is None:
        return None
    return float(Decimal(value))


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def timeline(status: str) -> list[dict]:
    current_index = 0
    for index, (_, _, statuses) in enumerate(TIMELINE):
        if status in statuses:
            current_index = index
            break
    items = []
    for index, (key, title, _) in enumerate(TIMELINE):
        if status in {"REJECTED", "CANCELLED"} and key == "deal":
            state = "skipped"
        elif index < current_index:
            state = "complete"
        elif index == current_index:
            state = "failed" if status in {"REJECTED", "CANCELLED"} else "current"
        else:
            state = "upcoming"
        items.append({"key": key, "title": title, "state": state})
    return items


def _decision_block(application, score, *, staff: bool) -> dict | None:
    if score is None:
        return None
    visible = staff or application.status in {
        "APPROVED",
        "APPROVED_WITH_CHANGES",
        "REJECTED",
        "CONTRACTING",
        "ISSUED",
        "NEED_INFO",
        "DECISION_READY",
    }
    if not visible:
        return None
    changes = []
    if application.status == "APPROVED_WITH_CHANGES" and score.offered_amount is not None:
        pairs = [
            ("Сумма", _num(application.amount), _num(score.offered_amount), "₽"),
            ("Срок", application.term_months, score.offered_term_months, "мес."),
            ("Ставка", None, _num(score.offered_rate), "%"),
        ]
        if pairs[0][1] != pairs[0][2]:
            changes.append({"field": "Сумма", "requested": pairs[0][1], "offered": pairs[0][2]})
        if pairs[1][1] != pairs[1][2]:
            changes.append({"field": "Срок", "requested": pairs[1][1], "offered": pairs[1][2]})
        product = get_product(application.product_code)
        if _num(score.offered_rate) != float(product.base_rate):
            changes.append({"field": "Ставка", "requested": float(product.base_rate), "offered": _num(score.offered_rate)})
    hide_terms = not staff and application.status == "DECISION_READY"
    block = {
        "score": score.score,
        "financial_position": score.financial_position,
        "financial_position_label": POSITION_LABEL.get(score.financial_position, score.financial_position),
        "debt_service": score.debt_service,
        "debt_service_label": SERVICE_LABEL.get(score.debt_service, score.debt_service),
        "quality_category": score.quality_category,
        "decision": score.decision,
        "offered_amount": None if hide_terms else _num(score.offered_amount),
        "offered_term_months": None if hide_terms else score.offered_term_months,
        "offered_rate": None if hide_terms else _num(score.offered_rate),
        "monthly_payment": None if hide_terms else _num(score.monthly_payment),
        "explanation": score.explanation if staff else score.client_explanation,
        "stop_factors": score.stop_factors_json or [],
        "awaits_employee": bool(score.awaits_employee and application.status == "DECISION_READY"),
        "changes": changes,
        "model_note": "Упрощённая правиловая модель по мотивам 590-П. Категория качества здесь — способ объяснить кредитное решение. Резервы не рассчитываются.",
    }
    if staff:
        block["factors"] = score.factors_json or []
    return block


def _company_view(application) -> dict:
    company = application.company
    registry = {}
    for item in reversed(application.checks):
        if item.source == "EGRUL" and item.status == "SUCCESS":
            registry = item.response_json or {}
            break
    status = company.registry_status or registry.get("status")
    labels = {
        "ACTIVE": "Действует",
        "LIQUIDATING": "В процессе ликвидации",
        "LIQUIDATED": "Ликвидирована",
    }
    source = registry.get("data_source")
    return {
        "inn": company.inn,
        "name": company.name,
        "full_name": registry.get("full_name"),
        "legal_form": company.legal_form,
        "ogrn": company.ogrn,
        "kpp": registry.get("kpp") or "",
        "registry_status": status,
        "registry_status_label": labels.get(status or "", status),
        "director_name": company.director_name,
        "address": company.address,
        "region": registry.get("region") or company.address,
        "registration_date": _iso(company.registration_date) or registry.get("registration_date"),
        "data_source": source,
        "source_label": (
            "Открытые сведения ФНС, egrul.nalog.ru"
            if source == "egrul.nalog.ru"
            else "Демонстрационная запись"
            if source == "demo"
            else None
        ),
    }


def application_view(application, *, staff: bool) -> dict:
    product = get_product(application.product_code)
    purpose = purposes().get(application.purpose)
    score = application.scores[-1] if application.scores else None
    pending = next((item for item in reversed(application.info_requests) if item.answer is None), None)
    contract = application.contracts[-1] if application.contracts else None
    done, now, nxt = STAGES[application.status]
    failed = any(item.status == "FAILED" for item in application.checks)
    awaits = application.status == "DECISION_READY" or (application.status == "ENRICHING" and failed)
    payload = {
        "id": str(application.id),
        "public_number": application.public_number,
        "status": application.status,
        "status_label": STATUS_LABELS[application.status],
        "stage": {"done": done, "now": now, "next_actor": nxt},
        "timeline": timeline(application.status),
        "purpose": application.purpose,
        "purpose_label": purpose.title if purpose else application.purpose,
        "product_code": application.product_code,
        "product_name": product.title,
        "amount": _num(application.amount),
        "term_months": application.term_months,
        "monthly_revenue": _num(application.monthly_revenue),
        "monthly_expenses": _num(application.monthly_expenses),
        "comment": application.comment or "",
        "created_at": _iso(application.created_at),
        "updated_at": _iso(application.updated_at),
        "awaits_employee": awaits,
        "company": _company_view(application),
        "events": [
            {
                "id": str(item.id),
                "from_status": item.from_status,
                "to_status": item.to_status,
                "actor_type": item.actor_type,
                "message": item.message,
                "created_at": _iso(item.created_at),
            }
            for item in application.events
        ],
        "decision": _decision_block(application, score, staff=staff),
        "pending_question": None if pending is None else pending.question,
        "contract_status": None if contract is None else contract.status,
        "contract_terms": None if contract is None else contract.terms_json,
    }
    if staff:
        payload["checks"] = [
            {
                "id": str(item.id),
                "source": item.source,
                "status": item.status,
                "response": item.response_json,
                "created_at": _iso(item.created_at),
            }
            for item in application.checks
        ]
        payload["scores"] = [
            {
                "id": str(item.id),
                "score": item.score,
                "quality_category": item.quality_category,
                "decision": item.decision,
                "explanation": item.explanation,
                "created_at": _iso(item.created_at),
            }
            for item in application.scores
        ]
    return payload


def application_brief(application) -> dict:
    failed = any(item.status == "FAILED" for item in application.checks)
    return {
        "id": str(application.id),
        "public_number": application.public_number,
        "status": application.status,
        "status_label": STATUS_LABELS[application.status],
        "company_name": application.company.name,
        "inn": application.company.inn,
        "product_name": get_product(application.product_code).title,
        "amount": _num(application.amount),
        "created_at": _iso(application.created_at),
        "awaits_employee": application.status == "DECISION_READY" or (application.status == "ENRICHING" and failed),
    }
