from datetime import date
from decimal import Decimal

import httpx
import pytest
from anthropic import APIConnectionError
from pydantic import ValidationError

from app import llm
from app.config import get_settings
from app.labels import label
from app.llm import is_acceptable, mock_description
from app.models import Car
from app.schemas import CarCreate, LoginIn
from tests.conftest import car_payload


def make_car(**changes: object) -> Car:
    values = {
        "make": "Skoda",
        "model": "Octavia",
        "year": 2021,
        "category": "compact",
        "transmission": "automatic",
        "fuel_type": "diesel",
        "seats": 5,
        "city": "Peja",
        "features": ["gps", "air_conditioning"],
        **changes,
    }
    return Car(**values)


def test_mock_description_follows_the_rules() -> None:
    car = make_car()
    text = mock_description(car)
    assert is_acceptable(text, car)
    assert "an automatic diesel compact" in text
    assert "GPS" in text


@pytest.mark.parametrize(
    "text",
    [
        "A nice car for 30 EUR per day: 2021 Skoda Octavia.",
        "2021 Skoda Octavia, only $45.",
        "A Skoda without a model year.",
        "",
        "2021 Skoda Octavia " + "x" * 600,
    ],
)
def test_guardrails_reject_bad_model_output(text: str) -> None:
    assert not is_acceptable(text, make_car())


def test_car_input_is_normalized() -> None:
    car = CarCreate.model_validate(car_payload(license_plate="  01-234  ab ", features=["gps", "gps"]))
    assert car.license_plate == "01-234 AB"
    assert car.features == ["gps"]
    assert car.daily_price == Decimal("50.00")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("year", date.today().year + 2),
        ("year", 1989),
        ("daily_price", 0),
        ("daily_price", 12.345),
        ("seats", 10),
        ("license_plate", "AB/12"),
        ("features", ["jetpack"]),
    ],
)
def test_car_input_is_validated(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CarCreate.model_validate(car_payload(**{field: value}))


def test_reserved_test_domain_is_accepted_and_bad_emails_are_not() -> None:
    assert LoginIn(email="Admin1@DriveNow.test", password="x").email == "admin1@drivenow.test"
    with pytest.raises(ValidationError):
        LoginIn(email="not-an-email", password="x")


def test_labels() -> None:
    assert label("air_conditioning") == "Air conditioning"
    assert label("suv") == "SUV"


def test_guardrails_reject_markdown() -> None:
    car = make_car()
    assert not is_acceptable("**2021 Skoda Octavia** in Peja", car)
    assert not is_acceptable("# 2021 Skoda Octavia\nNice car", car)
    assert not is_acceptable("2021 Skoda Octavia:\n- GPS\n- air conditioning", car)


async def test_llm_errors_fall_back_to_the_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_call(car: Car, api_key: str) -> str:
        raise APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(llm, "_anthropic_description", failing_call)

    text, provider = await llm.generate_description(make_car())

    assert provider == "mock"
    assert is_acceptable(text, make_car())
