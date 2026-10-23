import time

import httpx

SEARCH_URL = "https://pb.nalog.ru/search-proc.json"
COMPANY_URL = "https://pb.nalog.ru/company-proc.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://pb.nalog.ru",
    "Referer": "https://pb.nalog.ru/search.html",
    "X-Requested-With": "XMLHttpRequest",
}


class PbLookupError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def fetch_transparent(inn: str) -> dict:
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=HEADERS) as client:
            row = _search(client, inn)
            card = _company(client, row.get("token") or "")
    except PbLookupError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise PbLookupError("Сервис «Прозрачный бизнес» сейчас не ответил.", "unavailable") from exc
    return normalize_transparent(row, card)


def normalize_transparent(row: dict, card: dict | None = None) -> dict:
    card = card or {}
    vyp = card.get("vyp") if isinstance(card.get("vyp"), dict) else {}
    status_name = str(vyp.get("sulst_name_ex") or row.get("sulst_name_ex") or "")
    liquidated = bool(card.get("liquidated")) or str(row.get("pr_liq") or "0") == "1" or "ликвид" in status_name.lower() or "прекрат" in status_name.lower()
    mass = card.get("masaddress") if isinstance(card.get("masaddress"), list) else []
    employees = _published_number(card, ("sschr", "rnsschr", "avgsschr"))
    tax_amount = _published_number(card, ("arrear", "taxarrear", "nedoimka")) or 0
    income = _published_number(card, ("s2110", "2110", "revenue"))
    expense = _published_number(card, ("s2120", "2120", "expense"))
    okved_code = str(vyp.get("КодОКВЭД") or row.get("okved2main") or "")
    okved_name = str(vyp.get("НаимОКВЭД") or row.get("okved2mainname") or "")
    address = str(vyp.get("АдресРФ") or vyp.get("Адрес") or row.get("regionname") or "")
    return {
        "tax_regime": _tax_regime(card),
        "employees_count": employees,
        "income_last_year": income,
        "expense_last_year": expense,
        "tax_debt": tax_amount > 0,
        "tax_debt_amount": tax_amount,
        "suspended_accounts": False,
        "bankruptcy_procedure": None,
        "synthetic": False,
        "data_source": "pb.nalog.ru",
        "short_name": str(vyp.get("НаимЮЛСокр") or row.get("namec") or ""),
        "full_name": str(vyp.get("НаимЮЛПолн") or row.get("namep") or ""),
        "okved": f"{okved_code} {okved_name}".strip(),
        "address": address,
        "region": str(vyp.get("НаимРегион") or row.get("regionname") or ""),
        "kpp": str(vyp.get("КПП") or ""),
        "charter_capital": _money_amount(vyp.get("СумКап")),
        "status_name": status_name,
        "liquidated": liquidated,
        "mass_address_count": len(mass),
        "employees_published": bool(card.get("is_p_sschr")),
        "taxes_published": bool(card.get("is_p_taxpay")),
        "statements_published": bool(card.get("is_p_form1")),
        "arrears_published": bool(card.get("is_p_arrear")),
        "source_label": "Открытые сведения ФНС, сервис «Прозрачный бизнес»",
        "note": _note(card, employees, tax_amount, len(mass)),
    }


def _search(client: httpx.Client, inn: str) -> dict:
    payload = {
        "page": "1",
        "pageSize": "10",
        "pbCaptchaToken": "",
        "token": "",
        "mode": "search-all",
        "queryAll": inn,
        "queryUl": "",
    }
    started = client.post(SEARCH_URL, data=payload).json()
    if started.get("captchaRequired") or not started.get("id"):
        raise PbLookupError("«Прозрачный бизнес» попросил проверку. Повторите поиск через минуту.", "captcha")
    payload.update({"token": started["id"], "id": started["id"], "method": "get-response"})
    found = None
    for _ in range(5):
        time.sleep(0.8)
        raw = client.post(SEARCH_URL, data=payload).json()
        if isinstance(raw, dict) and (raw.get("ul") or raw.get("ip") or raw.get("captchaRequired")):
            found = raw
            break
    if not isinstance(found, dict):
        raise PbLookupError("«Прозрачный бизнес» не успел ответить. Повторите поиск.", "unavailable")
    if found.get("captchaRequired"):
        raise PbLookupError("«Прозрачный бизнес» попросил проверку. Повторите поиск через минуту.", "captcha")
    rows = []
    for kind in ("ul", "ip"):
        rows.extend((found.get(kind) or {}).get("data") or [])
    exact = [row for row in rows if str(row.get("inn") or "") == inn]
    if not exact:
        raise PbLookupError("В «Прозрачном бизнесе» нет карточки с таким ИНН.", "not_found")
    return exact[0]


def _company(client: httpx.Client, token: str) -> dict:
    if not token:
        return {}
    started = client.post(COMPANY_URL, data={"token": token, "method": "get-request"}).json()
    if started.get("captchaRequired"):
        raise PbLookupError("«Прозрачный бизнес» попросил проверку. Повторите поиск через минуту.", "captcha")
    current = started
    for _ in range(4):
        if isinstance(current, dict) and current.get("vyp"):
            return current
        time.sleep(0.4)
        current = client.post(
            COMPANY_URL,
            data={"token": current.get("token") or token, "id": current.get("id", ""), "method": "get-response"},
        ).json()
        if current.get("captchaRequired"):
            raise PbLookupError("«Прозрачный бизнес» попросил проверку. Повторите поиск через минуту.", "captcha")
    return current if isinstance(current, dict) else {}


def _tax_regime(card: dict) -> str:
    block = card.get("taxmode") or card.get("taxmodes") or card.get("spec")
    if isinstance(block, list) and block:
        first = block[0]
        if isinstance(first, dict):
            return str(first.get("name") or first.get("taxmode") or "опубликован")
        return str(first)
    if isinstance(block, dict):
        return str(block.get("name") or "опубликован")
    if card.get("is_p_taxmode"):
        return "опубликован, режим не разобран"
    return "ФНС не публикует режим на карточке"


def _published_number(card: dict, keys: tuple[str, ...]) -> int:
    wanted = {key.lower() for key in keys}
    found = _walk_number(card, wanted)
    return found or 0


def _walk_number(value, wanted: set[str]) -> int | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in wanted and _as_int(item) is not None:
                return _as_int(item)
            nested = _walk_number(item, wanted)
            if nested is not None:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _walk_number(item, wanted)
            if nested is not None:
                return nested
    return None


def _as_int(value) -> int | None:
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        return None
    text = str(value).replace(" ", "").replace(",", ".")
    if not text or text in {"0", "0.0"}:
        return 0 if text else None
    try:
        return int(float(text))
    except ValueError:
        return None


def _money_amount(value) -> int | None:
    amount = _as_int(value)
    if amount is None:
        return None
    return amount


def _note(card: dict, employees: int, tax_amount: int, mass_count: int) -> str:
    parts = ["Карточка открытого сервиса ФНС «Прозрачный бизнес»."]
    if employees:
        parts.append(f"Среднесписочная численность: {employees}.")
    elif not card.get("is_p_sschr"):
        parts.append("Численность на карточке не опубликована.")
    if tax_amount:
        parts.append(f"Опубликована налоговая задолженность: {tax_amount} ₽.")
    elif not card.get("is_p_arrear"):
        parts.append("Сведения о недоимке на карточке не опубликованы.")
    if mass_count:
        parts.append(f"По адресу указано связанных организаций: {mass_count}.")
    if not card.get("is_p_form1"):
        parts.append("Бухотчётность на карточке не опубликована.")
    return " ".join(parts)
