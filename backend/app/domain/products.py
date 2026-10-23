from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Product:
    code: str
    title: str
    summary: str
    min_amount: Decimal
    max_amount: Decimal
    min_term: int
    max_term: int
    base_rate: Decimal

    def clamp_amount(self, amount: Decimal) -> Decimal:
        return min(max(amount, self.min_amount), self.max_amount)

    def clamp_term(self, term: int) -> int:
        return min(max(term, self.min_term), self.max_term)

    def fits(self, amount: Decimal, term: int) -> bool:
        return self.min_amount <= amount <= self.max_amount and self.min_term <= term <= self.max_term


@dataclass(frozen=True)
class Purpose:
    code: str
    title: str
    product_code: str


@dataclass(frozen=True)
class OfferCard:
    product: Product
    fits: bool
    suggested_amount: Decimal
    suggested_term: int
    reason: str
    recommended: bool


@lru_cache
def _raw() -> dict:
    path = Path(__file__).with_name("products.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def products() -> dict[str, Product]:
    result = {}
    for code, item in _raw()["products"].items():
        result[code] = Product(
            code=code,
            title=item["title"],
            summary=item["summary"],
            min_amount=Decimal(str(item["min_amount"])),
            max_amount=Decimal(str(item["max_amount"])),
            min_term=int(item["min_term"]),
            max_term=int(item["max_term"]),
            base_rate=Decimal(str(item["base_rate"])),
        )
    return result


def purposes() -> dict[str, Purpose]:
    return {
        code: Purpose(code=code, title=item["title"], product_code=item["product"])
        for code, item in _raw()["purposes"].items()
    }


def get_product(code: str) -> Product:
    try:
        return products()[code]
    except KeyError as exc:
        raise KeyError(f"Неизвестный продукт {code}") from exc


def _card(product: Product, amount: Decimal, term: int, reason: str, recommended: bool) -> OfferCard:
    return OfferCard(
        product=product,
        fits=product.fits(amount, term),
        suggested_amount=product.clamp_amount(amount),
        suggested_term=product.clamp_term(term),
        reason=reason,
        recommended=recommended,
    )


def _on_border(purpose: str, amount: Decimal, term: int) -> str | None:
    """Второй продукт, если запрос рядом с соседним коридором."""
    catalog = products()
    if purpose == "UNKNOWN":
        return "TURNOVER" if amount <= catalog["TURNOVER"].max_amount else "DEVELOPMENT"
    if purpose == "TURNOVER" and term <= 12 and amount <= catalog["OVERDRAFT"].max_amount:
        return "OVERDRAFT"
    if purpose == "DEVELOPMENT" and term <= 36 and amount <= catalog["TURNOVER"].max_amount:
        return "TURNOVER"
    if purpose == "CASH_GAP" and amount >= catalog["LINE"].min_amount:
        return "LINE"
    return None


def recommend(purpose_code: str, amount: Decimal, term_months: int) -> tuple[OfferCard, OfferCard | None]:
    purpose = purposes()[purpose_code]
    catalog = products()
    primary = catalog[purpose.product_code]
    primary_card = _card(
        primary,
        amount,
        term_months,
        f"Для цели «{purpose.title}» подходит {primary.title.lower()}. {primary.summary}",
        True,
    )
    alt_code = _on_border(purpose_code, amount, term_months)
    if alt_code is None or alt_code == primary.code:
        return primary_card, None
    alternative = catalog[alt_code]
    alt_card = _card(
        alternative,
        amount,
        term_months,
        f"Рядом по сумме или сроку лежит {alternative.title.lower()}. {alternative.summary}",
        False,
    )
    return primary_card, alt_card
