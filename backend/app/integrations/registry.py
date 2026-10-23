import copy
from datetime import date

from app.integrations.egrul_nalog import describe_inn, fetch_egrul
from app.integrations.pb_nalog import PbLookupError, fetch_transparent
from app.mocks import lookup
from app.mocks.fixtures import FAIL_INN, demo_fixtures

CREDIT_HISTORY_NOTE = (
    "Кредитную историю по ИНН из открытых источников получить нельзя. "
    "НБКИ, ОКБ и Скоринг Бюро выдают отчёт только с согласия самой компании или кредитору. "
    "Поэтому для настоящего ИНН бюро не запрашивается и чистая история не подставляется."
)


def resolve_bundle(inn: str, as_of: date | None = None) -> dict[str, dict]:
    """Демо-ИНН остаются на фикстурах. Настоящий ИНН: ЕГРЮЛ и «Прозрачный бизнес» с сайтов ФНС."""
    today = as_of or date.today()
    if inn == FAIL_INN or inn in demo_fixtures(today):
        bundle = lookup(inn, today)
        bundle["EGRUL"]["data_source"] = "demo"
        bundle["BKI"]["available"] = True
        bundle["FNS"]["data_source"] = "demo"
        return bundle

    record = fetch_egrul(inn)
    try:
        transparent = fetch_transparent(inn)
    except PbLookupError as exc:
        transparent = _empty_transparent(str(exc))
    _merge_registry(record, transparent)
    return {
        "EGRUL": record,
        "BKI": {
            "active_count": None,
            "total_debt": None,
            "total_monthly_payment": 0,
            "max_overdue_days": 0,
            "loans": [],
            "available": False,
            "synthetic": False,
            "data_source": "unavailable",
            "note": CREDIT_HISTORY_NOTE,
        },
        "FNS": transparent,
    }


def company_profile(inn: str) -> dict:
    card = describe_inn(inn)
    if card["source"] == "demo":
        card["transparent"] = None
        card["credit_history"] = {
            "available": False,
            "note": "Это учебный ИНН. Кредитная история и «Прозрачный бизнес» для него синтетические и появятся после отправки заявки.",
        }
        return card
    try:
        transparent = fetch_transparent(inn)
    except PbLookupError as exc:
        card["transparent"] = None
        card["transparent_error"] = str(exc)
    else:
        card["transparent"] = copy.deepcopy(transparent)
        if transparent.get("address"):
            card["address"] = transparent["address"]
        if transparent.get("region"):
            card["region"] = transparent["region"]
    card["credit_history"] = {"available": False, "note": CREDIT_HISTORY_NOTE}
    return card


def _merge_registry(record: dict, transparent: dict) -> None:
    if transparent.get("address"):
        record["address"] = transparent["address"]
    if transparent.get("region"):
        record["region"] = transparent["region"]
    if transparent.get("okved"):
        record["okved"] = transparent["okved"].split(" ", 1)[0]
        record["okved_name"] = transparent["okved"]
    if transparent.get("charter_capital"):
        record["charter_capital"] = transparent["charter_capital"]
    if transparent.get("kpp"):
        record["kpp"] = transparent["kpp"]
    if transparent.get("liquidated"):
        record["status"] = "LIQUIDATED"
    if transparent.get("mass_address_count", 0) >= 10:
        record["unreliable_address"] = True


def _empty_transparent(message: str) -> dict:
    return {
        "tax_regime": "нет данных",
        "employees_count": 0,
        "income_last_year": 0,
        "expense_last_year": 0,
        "tax_debt": False,
        "tax_debt_amount": 0,
        "suspended_accounts": False,
        "bankruptcy_procedure": None,
        "synthetic": False,
        "data_source": "pb.nalog.ru",
        "note": message,
        "source_label": "Сервис «Прозрачный бизнес» не ответил",
    }
