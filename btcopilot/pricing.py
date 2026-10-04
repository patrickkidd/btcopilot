"""What a model call costs, in US dollars per million tokens, or per hour of
audio for a transcription."""

from dataclasses import dataclass
from decimal import Decimal

from btcopilot.modelturn import Spent
from btcopilot.llmutil import local_model

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input: Decimal
    output: Decimal
    cache_write: Decimal
    cache_read: Decimal


FREE = Price(Decimal(0), Decimal(0), Decimal(0), Decimal(0))
OPUS = Price(Decimal("5.00"), Decimal("25.00"), Decimal("6.25"), Decimal("0.50"))
FLASH = Price(Decimal("0.75"), Decimal("3.75"), Decimal(0), Decimal("0.075"))

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
    # Google's paid-tier text rates, ai.google.dev/gemini-api/docs/pricing, read
    # 2026-09-28. The 3.6 to 3.8 Flash rates double on 2027-01-01. Gemini keeps
    # its cache without a write charge; thinking is billed as output.
    "gemini-3.1-pro": Price(
        Decimal("2.00"), Decimal("12.00"), Decimal(0), Decimal("0.20")
    ),
    "gemini-3.8-flash": FLASH,
    "gemini-3.7-flash": FLASH,
    "gemini-3.6-flash": FLASH,
    "gemini-3.5-flash": Price(
        Decimal("1.50"), Decimal("9.00"), Decimal(0), Decimal("0.15")
    ),
    "gemini-2.5-flash": Price(
        Decimal("0.30"), Decimal("2.50"), Decimal(0), Decimal("0.03")
    ),
    # ai.google.dev/gemini-api/docs/pricing, read 2026-09-30 (text rates).
    "gemini-3.1-flash-lite": Price(
        Decimal("0.25"), Decimal("1.50"), Decimal(0), Decimal("0.025")
    ),
    "gemini-2.5-flash-lite": Price(
        Decimal("0.10"), Decimal("0.40"), Decimal(0), Decimal("0.01")
    ),
    # developers.openai.com/api/docs/pricing, read 2026-09-30. Cache writes
    # are 1.25x the input rate, developers.openai.com/api/docs/guides/prompt-caching.
    "gpt-6.1-sol": Price(
        Decimal("2.00"), Decimal("10.00"), Decimal("2.50"), Decimal("0.10")
    ),
}


# AssemblyAI's pre-recorded rates, assemblyai.com/pricing, read 2026-09-30:
# universal-3-5-pro $0.21 and universal-2 $0.15 an hour, each with the standard
# speaker labels every request asks for (+$0.02 an hour).
HOURLY = {
    "universal-3-5-pro": Decimal("0.23"),
    "universal-2": Decimal("0.17"),
}


def heard(model: str, seconds: float) -> Decimal:
    return HOURLY[model] * Decimal(str(seconds)) / 3600


def price(model: str) -> Price:
    if model == local_model():
        return FREE
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
