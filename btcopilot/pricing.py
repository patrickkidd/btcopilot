"""What a model call costs, in US dollars per million tokens."""

from dataclasses import dataclass
from decimal import Decimal

from btcopilot.coachmodel import Spent

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input: Decimal
    output: Decimal
    cache_write: Decimal
    cache_read: Decimal


OPUS = Price(Decimal("5.00"), Decimal("25.00"), Decimal("6.25"), Decimal("0.50"))

PRICES = {
    "claude-opus-4-6": OPUS,
    "claude-opus-4-8": OPUS,
    "claude-opus-5": OPUS,
    "claude-opus-5-5": Price(
        Decimal("4.00"), Decimal("20.00"), Decimal("5.00"), Decimal("0.20")
    ),
    "claude-sonnet-5": Price(
        Decimal("2.00"), Decimal("10.00"), Decimal("2.50"), Decimal("0.20")
    ),
    "claude-haiku-4-5": Price(
        Decimal("1.00"), Decimal("5.00"), Decimal("1.25"), Decimal("0.10")
    ),
}


def price(model: str) -> Price:
    matches = [prefix for prefix in PRICES if model.startswith(prefix)]
    if not matches:
        raise KeyError(f"No price for model {model}")
    return PRICES[max(matches, key=len)]


def cost(model: str, spent: Spent) -> Decimal:
    rate = price(model)
    return (
        spent.input * rate.input
        + spent.output * rate.output
        + spent.cache_creation * rate.cache_write
        + spent.cache_read * rate.cache_read
    ) / MILLION
