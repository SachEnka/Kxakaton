from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.products import recommend
from app.domain.scoring import annuity_payment, evaluate, max_principal
from app.domain.scoring import ScoreInput
from app.domain.state_machine import TransitionError, ensure_transition
from app.mocks import lookup


def _input(as_of, age_days, overdue, revenue=5_000_000, amount=300_000, bankruptcy=None, status="ACTIVE", term=18):
    registered = as_of - timedelta(days=age_days)
    return ScoreInput(
        amount=Decimal(amount),
        term_months=term,
        monthly_revenue=Decimal(revenue),
        product_code="TURNOVER",
        as_of=as_of,
        egrul={
            "status": status,
            "registration_date": registered.isoformat(),
            "unreliable_address": False,
            "unreliable_director": False,
        },
        bki={"total_monthly_payment": 0, "max_overdue_days": overdue, "loans": []},
        fns={
            "tax_debt": False,
            "tax_debt_amount": 0,
            "suspended_accounts": False,
            "bankruptcy_procedure": bankruptcy,
        },
    )


def test_quality_matrix():
    today = date(2026, 10, 23)
    ages = {"GOOD": 1200, "AVERAGE": 400, "POOR": 50}
    services = {"GOOD": 0, "AVERAGE": 10, "POOR": 45}
    expected = {
        ("GOOD", "GOOD"): "I",
        ("GOOD", "AVERAGE"): "II",
        ("GOOD", "POOR"): "III",
        ("AVERAGE", "GOOD"): "II",
        ("AVERAGE", "AVERAGE"): "III",
        ("AVERAGE", "POOR"): "IV",
        ("POOR", "GOOD"): "III",
        ("POOR", "AVERAGE"): "IV",
        ("POOR", "POOR"): "V",
    }
    for position, age in ages.items():
        for service, overdue in services.items():
            result = evaluate(_input(today, age, overdue))
            assert result.stop_factors == []
            assert result.financial_position == position
            assert result.debt_service == service
            assert result.quality_category == expected[(position, service)]


def test_bankruptcy_is_stop_even_with_strong_revenue():
    result = evaluate(_input(date(2026, 10, 23), 1200, 0, bankruptcy="COMPETITION"))
    assert result.quality_category == "V"
    assert result.decision == "REJECTED"
    assert any("банкрот" in item.lower() for item in result.stop_factors)


def test_annuity_inverse_stays_within_target():
    target = Decimal("60000")
    principal = max_principal(target, Decimal("25"), 24)
    payment = annuity_payment(principal, Decimal("25"), 24)
    assert payment <= target


def test_forbidden_transition():
    with pytest.raises(TransitionError):
        ensure_transition("ISSUED", "DRAFT", "SYSTEM")
    with pytest.raises(TransitionError):
        ensure_transition("ISSUED", "REJECTED", "UNDERWRITER")


def test_product_recommendation_follows_purpose():
    amount = Decimal("1500000")
    assert recommend("TURNOVER", amount, 18)[0].product.code == "TURNOVER"
    assert recommend("DEVELOPMENT", amount, 24)[0].product.code == "DEVELOPMENT"
    assert recommend("CASH_GAP", amount, 6)[0].product.code == "OVERDRAFT"
    assert recommend("UNKNOWN", amount, 18)[0].product.code == "LINE"


def test_rate_keeps_trailing_zero_in_tens():
    from app.domain.scoring import _rate

    assert _rate(Decimal("20")) == "20%"
    assert _rate(Decimal("22.5")) == "22.5%"
    data = _input(date(2026, 10, 23), 1200, 0)
    data.bki["available"] = False
    result = evaluate(data)
    assert result.debt_service == "AVERAGE"
    assert any("бюро" in item.detail for item in result.factors)


def test_demo_profiles_produce_four_outcomes():
    today = date.today()
    approved = evaluate(
        ScoreInput(
            amount=Decimal(1_500_000),
            term_months=18,
            monthly_revenue=Decimal(800_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=lookup("7700000001", today)["EGRUL"],
            bki=lookup("7700000001", today)["BKI"],
            fns=lookup("7700000001", today)["FNS"],
        )
    )
    assert approved.decision == "APPROVED"
    assert approved.quality_category == "I"
    assert approved.offered_amount == Decimal(1_500_000)
    assert approved.offered_rate == Decimal("20")

    changed = evaluate(
        ScoreInput(
            amount=Decimal(5_000_000),
            term_months=24,
            monthly_revenue=Decimal(400_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=lookup("7700000002", today)["EGRUL"],
            bki=lookup("7700000002", today)["BKI"],
            fns=lookup("7700000002", today)["FNS"],
        )
    )
    assert changed.decision == "APPROVED_WITH_CHANGES"
    assert changed.offered_amount is not None
    assert changed.offered_amount < Decimal(5_000_000)
    assert changed.offered_amount >= Decimal(300_000)

    rejected = evaluate(
        ScoreInput(
            amount=Decimal(2_000_000),
            term_months=24,
            monthly_revenue=Decimal(900_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=lookup("7700000003", today)["EGRUL"],
            bki=lookup("7700000003", today)["BKI"],
            fns=lookup("7700000003", today)["FNS"],
        )
    )
    assert rejected.decision == "REJECTED"
    assert rejected.quality_category == "V"

    overdue = evaluate(
        ScoreInput(
            amount=Decimal(800_000),
            term_months=12,
            monthly_revenue=Decimal(500_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=lookup("7700000004", today)["EGRUL"],
            bki=lookup("7700000004", today)["BKI"],
            fns=lookup("7700000004", today)["FNS"],
        )
    )
    assert overdue.decision == "REJECTED"
    assert any("просроч" in item.lower() for item in overdue.stop_factors)

    young = lookup("7700000005", today)
    question = evaluate(
        ScoreInput(
            amount=Decimal(1_500_000),
            term_months=18,
            monthly_revenue=Decimal(350_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=young["EGRUL"],
            bki=young["BKI"],
            fns=young["FNS"],
            clarified=False,
        )
    )
    assert question.decision == "NEED_INFO"
    assert question.info_question

    second = evaluate(
        ScoreInput(
            amount=Decimal(1_500_000),
            term_months=18,
            monthly_revenue=Decimal(350_000),
            product_code="TURNOVER",
            as_of=today,
            egrul=young["EGRUL"],
            bki=young["BKI"],
            fns=young["FNS"],
            clarified=True,
        )
    )
    assert second.decision != "NEED_INFO"
    assert second.awaits_employee is True
