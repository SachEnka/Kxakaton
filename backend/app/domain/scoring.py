from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from app.domain.products import get_product

POSITION_GOOD = "GOOD"
POSITION_AVERAGE = "AVERAGE"
POSITION_POOR = "POOR"
SERVICE_GOOD = "GOOD"
SERVICE_AVERAGE = "AVERAGE"
SERVICE_POOR = "POOR"

DECISION_APPROVED = "APPROVED"
DECISION_CHANGES = "APPROVED_WITH_CHANGES"
DECISION_REJECTED = "REJECTED"
DECISION_NEED_INFO = "NEED_INFO"

MATRIX = {
    (POSITION_GOOD, SERVICE_GOOD): "I",
    (POSITION_GOOD, SERVICE_AVERAGE): "II",
    (POSITION_GOOD, SERVICE_POOR): "III",
    (POSITION_AVERAGE, SERVICE_GOOD): "II",
    (POSITION_AVERAGE, SERVICE_AVERAGE): "III",
    (POSITION_AVERAGE, SERVICE_POOR): "IV",
    (POSITION_POOR, SERVICE_GOOD): "III",
    (POSITION_POOR, SERVICE_AVERAGE): "IV",
    (POSITION_POOR, SERVICE_POOR): "V",
}

POSITION_LABEL = {POSITION_GOOD: "хорошее", POSITION_AVERAGE: "среднее", POSITION_POOR: "плохое"}
SERVICE_LABEL = {SERVICE_GOOD: "хорошее", SERVICE_AVERAGE: "среднее", SERVICE_POOR: "плохое"}

MODEL_NOTE = (
    "Упрощённая правиловая модель по мотивам 590-П. "
    "Категория качества здесь — способ объяснить кредитное решение. Резервы не рассчитываются."
)


@dataclass
class Factor:
    code: str
    title: str
    detail: str


@dataclass
class ScoreInput:
    amount: Decimal
    term_months: int
    monthly_revenue: Decimal | None
    product_code: str
    as_of: date
    egrul: dict
    bki: dict
    fns: dict
    clarified: bool = False


@dataclass
class ScoreOutput:
    score: int
    financial_position: str
    debt_service: str
    quality_category: str
    stop_factors: list[str] = field(default_factory=list)
    factors: list[Factor] = field(default_factory=list)
    decision: str = DECISION_REJECTED
    offered_amount: Decimal | None = None
    offered_term_months: int | None = None
    offered_rate: Decimal | None = None
    monthly_payment: Decimal | None = None
    explanation: str = ""
    client_explanation: str = ""
    info_question: str | None = None
    awaits_employee: bool = False
    burden: Decimal | None = None


def annuity_payment(amount: Decimal, annual_rate_percent: Decimal, months: int) -> Decimal:
    r = (annual_rate_percent / Decimal(100)) / Decimal(12)
    if r == 0:
        return (amount / Decimal(months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    power = (Decimal(1) + r) ** months
    payment = amount * r * power / (power - Decimal(1))
    return payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def max_principal(payment: Decimal, annual_rate_percent: Decimal, months: int) -> Decimal:
    r = (annual_rate_percent / Decimal(100)) / Decimal(12)
    power = (Decimal(1) + r) ** months
    amount = payment * (power - Decimal(1)) / (r * power)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _money(value: Decimal) -> str:
    quantized = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(quantized):,}".replace(",", " ") + " ₽"


def _rate(value: Decimal) -> str:
    text = f"{value.quantize(Decimal('0.01')):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


def evaluate(data: ScoreInput) -> ScoreOutput:
    product = get_product(data.product_code)
    factors: list[Factor] = []
    stops: list[str] = []

    registry_status = data.egrul.get("status")
    if registry_status in {"LIQUIDATED", "LIQUIDATING"}:
        stops.append("Компания ликвидирована или находится в процессе ликвидации.")
    bankruptcy = data.fns.get("bankruptcy_procedure")
    if bankruptcy:
        stops.append("Компания находится в процедуре банкротства.")
    overdue = int(data.bki.get("max_overdue_days") or 0)
    if overdue > 90:
        stops.append(f"В смоделированной кредитной истории есть просрочка {overdue} дней.")
    if data.fns.get("suspended_accounts"):
        stops.append("Операции по счетам приостановлены.")
    if data.amount > product.max_amount:
        stops.append("Сумма выше верхней границы выбранного продукта.")

    raw_date = data.egrul.get("registration_date")
    age = months_between(date.fromisoformat(raw_date), data.as_of) if raw_date else 0
    revenue = data.monthly_revenue
    tax_amount = Decimal(str(data.fns.get("tax_debt_amount") or 0))
    tax_debt = bool(data.fns.get("tax_debt")) and tax_amount > 0
    unreliable_address = bool(data.egrul.get("unreliable_address"))
    unreliable_director = bool(data.egrul.get("unreliable_director"))
    revenue_missing = revenue is None or revenue <= 0

    poor_reasons = []
    if age < 6:
        poor_reasons.append(f"компания зарегистрирована {age} мес. назад")
    if tax_amount >= Decimal(100000):
        poor_reasons.append(f"налоговая задолженность {_money(tax_amount)}")
    if unreliable_address and unreliable_director:
        poor_reasons.append("недостоверны и адрес, и сведения о руководителе")
    if revenue_missing:
        poor_reasons.append("не указана ежемесячная выручка")

    good_ok = (
        registry_status == "ACTIVE"
        and age >= 24
        and not revenue_missing
        and not tax_debt
        and not unreliable_address
        and not unreliable_director
    )
    if poor_reasons:
        position = POSITION_POOR
        factors.append(Factor("position", "Финансовое положение", "Плохое: " + "; ".join(poor_reasons) + "."))
    elif good_ok:
        position = POSITION_GOOD
        factors.append(
            Factor(
                "position",
                "Финансовое положение",
                f"Хорошее: компания действует {age} мес., налоговая задолженность не найдена.",
            )
        )
    else:
        position = POSITION_AVERAGE
        notes = []
        if age < 24:
            notes.append(f"возраст компании {age} мес.")
        if tax_debt and tax_amount < Decimal(100000):
            notes.append(f"небольшая налоговая задолженность {_money(tax_amount)}")
        if unreliable_address ^ unreliable_director:
            notes.append("есть один признак недостоверных сведений")
        if registry_status != "ACTIVE":
            notes.append(f"статус в реестре {registry_status}")
        factors.append(
            Factor("position", "Финансовое положение", "Среднее" + (": " + "; ".join(notes) if notes else "."))
        )

    existing_payment = Decimal(str(data.bki.get("total_monthly_payment") or 0))
    requested_payment = annuity_payment(data.amount, product.base_rate, data.term_months)
    burden = None
    if not revenue_missing:
        burden = (existing_payment + requested_payment) / revenue

    if revenue_missing or overdue > 30 or (burden is not None and burden > Decimal("0.60")):
        service = SERVICE_POOR
        if revenue_missing:
            service_detail = "Плохое: без выручки нельзя оценить платёж."
        elif overdue > 30:
            service_detail = f"Плохое: просрочка {overdue} дней."
        else:
            service_detail = f"Плохое: платёж забирает {burden:.0%} выручки."
    elif overdue == 0 and burden is not None and burden <= Decimal("0.40") and data.bki.get("available", True):
        service = SERVICE_GOOD
        service_detail = f"Хорошее: просрочек нет, новый платёж занимает {burden:.0%} выручки."
    else:
        service = SERVICE_AVERAGE
        bits = []
        if not data.bki.get("available", True):
            bits.append("кредитная история не запрашивалась, бюро без согласия компании её не отдаёт")
        if overdue:
            bits.append(f"просрочка {overdue} дней")
        if burden is not None:
            bits.append(f"нагрузка {burden:.0%}")
        service_detail = "Среднее: " + ", ".join(bits) + "."
    factors.append(Factor("service", "Обслуживание долга", service_detail))

    category = "V" if stops else MATRIX[(position, service)]
    score = 100
    score -= 40 if position == POSITION_POOR else 15 if position == POSITION_AVERAGE else 0
    score -= 40 if service == SERVICE_POOR else 15 if service == SERVICE_AVERAGE else 0
    if stops:
        score -= 25
    score = max(0, min(100, score))

    decision = DECISION_REJECTED
    offered_amount: Decimal | None = None
    offered_term: int | None = None
    offered_rate: Decimal | None = None
    payment: Decimal | None = None
    question = None
    awaits = False
    outcome = ""

    if stops or category == "V":
        decision = DECISION_REJECTED
        outcome = stops[0] if stops else "Финансовое положение и обслуживание долга не позволяют выдать кредит."
    elif category == "I":
        decision = DECISION_APPROVED
        offered_amount, offered_term, offered_rate = data.amount, data.term_months, product.base_rate
        payment = annuity_payment(offered_amount, offered_rate, offered_term)
        outcome = f"Одобряем {_money(offered_amount)} на {offered_term} мес. по ставке {_rate(offered_rate)}."
    elif category == "II":
        decision = DECISION_APPROVED
        offered_rate = product.base_rate + Decimal(2)
        offered_amount, offered_term = data.amount, data.term_months
        payment = annuity_payment(offered_amount, offered_rate, offered_term)
        outcome = (
            f"Одобряем запрошенные {_money(offered_amount)} на {offered_term} мес. "
            f"Ставка {_rate(offered_rate)}: на 2 п.п. выше базовой из-за категории II."
        )
    elif category == "III":
        decision, offered_amount, offered_term, offered_rate, payment, outcome = _counter_offer(
            data, product, existing_payment, Decimal("0.40"), Decimal(5), category="III"
        )
    else:
        young_or_empty = age < 6 or revenue_missing
        if young_or_empty and not data.clarified:
            decision = DECISION_NEED_INFO
            if revenue_missing:
                question = "Укажите среднемесячную выручку компании в рублях и коротко напишите, из чего она складывается."
            else:
                question = (
                    "Компания зарегистрирована менее 6 месяцев. "
                    "Опишите, из чего складывается ежемесячная выручка и какой она была в последние месяцы."
                )
            outcome = "Пока не хватает данных, чтобы назвать сумму и ставку."
        else:
            awaits = True
            decision, offered_amount, offered_term, offered_rate, payment, outcome = _counter_offer(
                data, product, existing_payment, Decimal("0.30"), Decimal(5), category="IV"
            )
            if decision == DECISION_REJECTED:
                outcome = "Даже урезанный платёж не собирается в коридоре продукта. " + outcome

    client = _client_text(decision, outcome, question, awaits)
    staff = " ".join(
        [
            "Проверили регистрацию, налоговые признаки и смоделированную кредитную историю.",
            f"Финансовое положение — {POSITION_LABEL[position]}, обслуживание долга — {SERVICE_LABEL[service]}, категория {category}.",
            outcome,
            "Решение подтверждает сотрудник банка." if awaits else "",
            MODEL_NOTE,
        ]
    ).strip()

    return ScoreOutput(
        score=score,
        financial_position=position,
        debt_service=service,
        quality_category=category,
        stop_factors=stops,
        factors=factors,
        decision=decision,
        offered_amount=offered_amount,
        offered_term_months=offered_term,
        offered_rate=offered_rate,
        monthly_payment=payment,
        explanation=staff,
        client_explanation=client,
        info_question=question,
        awaits_employee=awaits,
        burden=burden,
    )


def _counter_offer(data: ScoreInput, product, existing_payment: Decimal, burden_cap: Decimal, addon: Decimal, category: str):
    rate = product.base_rate + addon
    term = data.term_months
    if product.code in {"TURNOVER", "LINE"}:
        term = min(term, 36)
    term = product.clamp_term(term)
    revenue = data.monthly_revenue or Decimal(0)
    max_payment = burden_cap * revenue - existing_payment
    if max_payment <= 0:
        return (
            DECISION_REJECTED,
            None,
            None,
            None,
            None,
            "Свободного платежа после текущих обязательств не остаётся.",
        )
    ceiling = max_principal(max_payment, rate, term)
    offered = min(data.amount, ceiling)
    if offered < product.min_amount:
        return (
            DECISION_REJECTED,
            None,
            None,
            None,
            None,
            f"Посильная сумма меньше минимума продукта ({_money(product.min_amount)}).",
        )
    payment = annuity_payment(offered, rate, term)
    if category == "III":
        text = (
            f"Можем предложить {_money(offered)} на {term} мес. по ставке {_rate(rate)}, "
            f"чтобы платёж оставался в пределах {int(burden_cap * 100)}% выручки."
        )
    else:
        text = (
            f"После уточнения посильная сумма — {_money(offered)} на {term} мес. по ставке {_rate(rate)}."
        )
    return (DECISION_CHANGES, offered, term, rate, payment, text)


def _client_text(decision: str, outcome: str, question: str | None, awaits: bool) -> str:
    if decision == DECISION_NEED_INFO:
        return outcome + " " + (question or "")
    if awaits and decision == DECISION_REJECTED:
        return "Автоматическая оценка не нашла посильных условий. Решение проверяет сотрудник банка. " + outcome
    if awaits:
        return "Оценка готова, сотрудник банка проверяет предложенные условия. " + outcome
    if decision == DECISION_REJECTED:
        return outcome + " Можно вернуться с другой суммой, когда обстоятельства изменятся."
    if decision == DECISION_CHANGES:
        return outcome + " Эти условия отличаются от исходного запроса."
    return outcome
