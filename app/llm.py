"""Car descriptions written by an LLM (Anthropic) or by a deterministic mock.

Guardrails apply to both: plain text, at most 600 characters, must name make, model and year, and
must never contain a price. A model answer that breaks a rule is replaced by the mock text.
"""

import logging
import re

from anthropic import AnthropicError, AsyncAnthropic

from app.config import get_settings
from app.labels import lower_label
from app.models import Car
from app.secrets import get_secrets

log = logging.getLogger(__name__)
MAX_LENGTH = 600
_PRICE = re.compile(r"(€|\$|£|\beur\b|\beuro|\busd\b|\bprice\b|\bper day\b)", re.IGNORECASE)
_MARKDOWN = re.compile(r"(\*\*|__|^\s*#|^\s*[-*] )", re.MULTILINE)

_PROMPT = """Write a short, friendly rental listing description for this car.
Rules: plain text, no markdown, at most 450 characters, mention the make, the model and the year
exactly as given, do not mention any price or money, do not invent features that are not listed.

Make: {make}
Model: {model}
Year: {year}
Category: {category}
Transmission: {transmission}
Fuel: {fuel}
Seats: {seats}
Features: {features}
City: {city}"""


def _readable(value: str) -> str:
    return lower_label(value)


def mock_description(car: Car) -> str:
    features = ", ".join(_readable(f) for f in car.features[:4])
    with_features = f" It comes with {features}." if features else ""
    kind = f"{_readable(car.transmission)} {_readable(car.fuel_type)} {_readable(car.category)}"
    article = "an" if kind[0] in "aeiou" else "a"
    return (
        f"{car.year} {car.make} {car.model}, {article} {kind} with {car.seats} seats, "
        f"ready for pickup in {car.city}.{with_features} "
        "Clean, well maintained and easy to drive."
    )


def is_acceptable(text: str, car: Car) -> bool:
    lowered = text.lower()
    return (
        0 < len(text) <= MAX_LENGTH
        and car.make.lower() in lowered
        and car.model.lower() in lowered
        and str(car.year) in text
        and not _PRICE.search(text)
        and not _MARKDOWN.search(text)
    )


async def _anthropic_description(car: Car, api_key: str) -> str:
    settings = get_settings()
    client = AsyncAnthropic(api_key=api_key, timeout=20)
    prompt = _PROMPT.format(
        make=car.make,
        model=car.model,
        year=car.year,
        category=_readable(car.category),
        transmission=car.transmission,
        fuel=car.fuel_type,
        seats=car.seats,
        features=", ".join(_readable(f) for f in car.features) or "none listed",
        city=car.city,
    )
    async with client:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
    return "".join(block.text for block in response.content if block.type == "text").strip()


async def generate_description(car: Car) -> tuple[str, str]:
    """Returns the description and the provider that wrote it."""
    if get_settings().llm_provider == "anthropic":
        api_key = get_secrets().get("anthropic-api-key")
        if api_key:
            try:
                text = await _anthropic_description(car, api_key)
            except AnthropicError:
                log.exception("the LLM call failed, using the mock description")
            else:
                if is_acceptable(text, car):
                    return text, "anthropic"
                log.warning("the LLM answer broke the rules, using the mock description: %r", text)
    return mock_description(car), "mock"
