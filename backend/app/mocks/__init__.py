import copy
import hashlib
from datetime import date, timedelta

from app.mocks.fixtures import FAIL_INN, demo_fixtures


class MockIntegrationError(Exception):
    pass


def _generated(inn: str, as_of: date) -> dict:
    digest = int(hashlib.sha256(inn.encode()).hexdigest(), 16)
    age_months = 18 + (digest % 30)
    registered = as_of - timedelta(days=age_months * 30)
    monthly = 10000 + (digest % 5) * 5000
    return {
        "egrul": {
            "full_name": f"Общество с ограниченной ответственностью «Демо {inn[-4:]}»",
            "short_name": f"ООО «Демо {inn[-4:]}»",
            "legal_form": "IP" if len(inn) == 12 else "OOO",
            "ogrn": str(10**12 + (digest % 10**12)).zfill(13)[:13],
            "status": "ACTIVE",
            "registration_date": registered.isoformat(),
            "okved": "47.19",
            "okved_name": "Торговля розничная прочая",
            "address": "г. Москва, синтетический адрес симулятора",
            "director_name": "Демонстрационный руководитель",
            "unreliable_address": False,
            "unreliable_director": False,
            "charter_capital": 10000,
        },
        "bki": {
            "active_count": 1,
            "total_debt": monthly * 10,
            "total_monthly_payment": monthly,
            "max_overdue_days": 0,
            "loans": [
                {
                    "type": "Кредит",
                    "opened_on": registered.isoformat(),
                    "amount": monthly * 20,
                    "balance": monthly * 10,
                    "monthly_payment": monthly,
                    "overdue_days": 0,
                    "status": "ACTIVE",
                }
            ],
        },
        "fns": {
            "tax_regime": "USN",
            "employees_count": 2,
            "income_last_year": monthly * 12 * 3,
            "expense_last_year": monthly * 12 * 2,
            "tax_debt": False,
            "tax_debt_amount": 0,
            "suspended_accounts": False,
            "bankruptcy_procedure": None,
        },
    }


def lookup(inn: str, as_of: date | None = None) -> dict[str, dict]:
    today = as_of or date.today()
    if inn == FAIL_INN:
        raise MockIntegrationError("Симулятор ЕГРЮЛ временно недоступен. Заявка остаётся на обогащении.")
    bundled = demo_fixtures(today).get(inn)
    if bundled is None:
        bundled = _generated(inn, today)
    return {
        "EGRUL": copy.deepcopy(bundled["egrul"]),
        "BKI": copy.deepcopy(bundled["bki"]),
        "FNS": copy.deepcopy(bundled["fns"]),
    }
