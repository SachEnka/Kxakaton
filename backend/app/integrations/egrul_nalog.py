from datetime import date

import httpx

from app.mocks.fixtures import demo_fixtures

SEARCH_URL = "https://egrul.nalog.ru/"
RESULT_URL = "https://egrul.nalog.ru/search-result/{token}"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://egrul.nalog.ru",
    "Referer": "https://egrul.nalog.ru/index.html",
    "X-Requested-With": "XMLHttpRequest",
}


class EgrulLookupError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_row(row: dict) -> dict:
    inn = str(row.get("i") or "")
    legal_form = "IP" if row.get("k") == "fl" or len(inn) == 12 else "OOO"
    director_raw = str(row.get("g") or "").strip()
    director_name = director_raw.split(":", 1)[1].strip() if ":" in director_raw else director_raw
    region = str(row.get("rn") or "").strip()
    address = str(row.get("a") or region).strip()
    terminated = bool(row.get("e") or row.get("endDate") or row.get("dt"))
    return {
        "full_name": str(row.get("n") or "").strip(),
        "short_name": str(row.get("c") or row.get("n") or "").strip(),
        "legal_form": legal_form,
        "ogrn": str(row.get("o") or "").strip(),
        "kpp": str(row.get("p") or "").strip(),
        "inn": inn,
        "status": "LIQUIDATED" if terminated else "ACTIVE",
        "registration_date": _iso_date(str(row.get("r") or "")),
        "okved": str(row.get("okved") or "").strip(),
        "okved_name": "",
        "address": address,
        "region": region,
        "director_name": director_name,
        "director_post": director_raw,
        "unreliable_address": False,
        "unreliable_director": False,
        "charter_capital": None,
        "data_source": "egrul.nalog.ru",
    }


def _iso_date(value: str) -> str | None:
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    day, month, year = parts
    if len(year) != 4:
        return None
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def fetch_egrul(inn: str) -> dict:
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=HEADERS) as client:
            started = client.post(SEARCH_URL, data={"query": inn})
            started.raise_for_status()
            payload = started.json()
            if payload.get("captchaRequired") or not payload.get("t"):
                raise EgrulLookupError(
                    "Сайт ФНС попросил проверку, что запрос делает человек. Повторите поиск через минуту.",
                    "captcha",
                )
            result = client.get(RESULT_URL.format(token=payload["t"]))
            result.raise_for_status()
            rows = result.json().get("rows") or []
    except EgrulLookupError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise EgrulLookupError("Сервис egrul.nalog.ru сейчас не ответил. Попробуйте ещё раз.", "unavailable") from exc

    exact = [row for row in rows if str(row.get("i") or "") == inn]
    if not exact:
        raise EgrulLookupError("В ЕГРЮЛ и ЕГРИП нет записи с таким ИНН.", "not_found")
    return normalize_row(exact[0])


def describe_inn(inn: str) -> dict:
    demo = demo_fixtures(date.today()).get(inn)
    if demo is not None:
        record = demo["egrul"]
        return _card(
            {
                **record,
                "inn": inn,
                "kpp": "",
                "region": record.get("address") or "",
                "director_post": record.get("director_name") or "",
            },
            source="demo",
        )
    return _card(fetch_egrul(inn), source="egrul.nalog.ru")


def _card(record: dict, source: str) -> dict:
    status = record.get("status") or "ACTIVE"
    labels = {
        "ACTIVE": "Действует",
        "LIQUIDATING": "В процессе ликвидации",
        "LIQUIDATED": "Ликвидирована",
    }
    source_label = (
        "Демонстрационная запись для тестового ИНН"
        if source == "demo"
        else "Открытые сведения ФНС, поиск на egrul.nalog.ru"
    )
    return {
        "found": True,
        "source": source,
        "source_label": source_label,
        "inn": record.get("inn") or "",
        "short_name": record.get("short_name") or "",
        "full_name": record.get("full_name") or "",
        "ogrn": record.get("ogrn") or "",
        "kpp": record.get("kpp") or "",
        "legal_form": record.get("legal_form") or "OOO",
        "director_name": record.get("director_name") or "",
        "director_post": record.get("director_post") or record.get("director_name") or "",
        "region": record.get("region") or record.get("address") or "",
        "address": record.get("address") or "",
        "registration_date": record.get("registration_date"),
        "status": status,
        "status_label": labels.get(status, status),
    }
