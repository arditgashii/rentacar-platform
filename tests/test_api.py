from datetime import date, timedelta

import httpx
import pytest

from app.messaging import MemoryEventBus
from tests.conftest import car_payload, login, png_bytes


async def test_health_and_ready(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": "ok", "storage": "ok", "bus": "ok"}
    # The QA dashboard reads when the demo data was seeded (null when it was never seeded).
    assert "seededAt" in ready.json()


async def test_register_then_login(client: httpx.AsyncClient) -> None:
    data = {"email": "New.Person@DriveNow.test", "password": "longenough", "full_name": "New Person"}
    created = await client.post("/api/v1/auth/register", json=data)
    assert created.status_code == 201
    assert created.json()["email"] == "new.person@drivenow.test"
    assert created.json()["role"] == "client"

    again = await client.post("/api/v1/auth/register", json=data)
    assert again.status_code == 409
    assert again.json()["code"] == "EMAIL_TAKEN"

    token = await client.post(
        "/api/v1/auth/login", json={"email": data["email"], "password": data["password"]}
    )
    assert token.status_code == 200


async def test_inactive_and_wrong_password_cannot_log_in(client: httpx.AsyncClient) -> None:
    inactive = await client.post(
        "/api/v1/auth/login", json={"email": "inactive@drivenow.test", "password": "DriveNow!2026"}
    )
    assert inactive.json()["code"] == "ACCOUNT_INACTIVE"
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "client1@drivenow.test", "password": "wrong-password"}
    )
    assert wrong.status_code == 401


async def test_update_keeps_the_exact_price(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()

    updated = await client.put(
        f"/api/v1/cars/{car['id']}", json=car_payload(daily_price=89.99), headers=owner
    )

    assert updated.status_code == 200
    assert updated.json()["daily_price"] == 89.99


async def test_patch_is_validated_like_put(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()

    response = await client.patch(f"/api/v1/cars/{car['id']}", json={"seats": 20}, headers=owner)

    assert response.status_code == 422
    assert "seats" in response.json()["detail"]


async def test_max_price_includes_the_limit(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(daily_price=63.21), headers=owner)).json()

    found = await client.get("/api/v1/cars", params={"min_price": 63.21, "max_price": 63.21})

    assert [item["id"] for item in found.json()["items"]] == [car["id"]]


async def test_overlapping_booking_is_refused(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    renter = await login(client, "client2@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()
    start = date.today() + timedelta(days=10)
    first = {"car_id": car["id"], "start_date": str(start), "end_date": str(start + timedelta(days=2))}
    assert (await client.post("/api/v1/bookings", json=first, headers=renter)).status_code == 201

    around = {
        "car_id": car["id"],
        "start_date": str(start - timedelta(days=1)),
        "end_date": str(start + timedelta(days=5)),
    }
    response = await client.post("/api/v1/bookings", json=around, headers=renter)

    assert response.status_code == 409
    assert response.json()["code"] == "DATES_TAKEN"


async def test_back_to_back_bookings_are_allowed(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    renter = await login(client, "client2@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()
    start = date.today() + timedelta(days=3)
    middle = start + timedelta(days=2)
    for begin, end in ((start, middle), (middle, middle + timedelta(days=2))):
        booking = {"car_id": car["id"], "start_date": str(begin), "end_date": str(end)}
        assert (await client.post("/api/v1/bookings", json=booking, headers=renter)).status_code == 201


async def test_booking_total_and_notifications(client: httpx.AsyncClient, bus: MemoryEventBus) -> None:
    owner = await login(client, "client3@drivenow.test")
    renter = await login(client, "client4@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(daily_price=33.33), headers=owner)).json()
    start = date.today() + timedelta(days=4)
    booking = await client.post(
        "/api/v1/bookings",
        json={"car_id": car["id"], "start_date": str(start), "end_date": str(start + timedelta(days=3))},
        headers=renter,
    )
    assert booking.json()["total_price"] == 99.99
    assert booking.json()["status"] == "pending"

    await bus.drain()
    owner_notes = (await client.get("/api/v1/notifications", headers=owner)).json()
    assert any(n["payload"]["booking_id"] == booking.json()["id"] for n in owner_notes)


async def test_client_cannot_delete_another_clients_car(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    other = await login(client, "client2@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()

    response = await client.delete(f"/api/v1/cars/{car['id']}", headers=other)

    assert response.status_code == 403
    assert (await client.get(f"/api/v1/cars/{car['id']}")).status_code == 200


async def test_photo_rules(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()
    url = f"/api/v1/cars/{car['id']}/photos"

    fake = await client.post(url, files={"file": ("x.jpg", b"not an image", "image/jpeg")}, headers=owner)
    assert fake.json()["code"] == "INVALID_IMAGE"

    first = (await client.post(url, files={"file": ("a.png", png_bytes())}, headers=owner)).json()
    second = (await client.post(url, files={"file": ("b.png", png_bytes())}, headers=owner)).json()
    assert first["is_primary"] and not second["is_primary"]
    assert (await client.get(first["url"])).headers["content-type"] == "image/png"

    await client.delete(f"{url}/{first['id']}", headers=owner)
    photos = (await client.get(f"/api/v1/cars/{car['id']}")).json()["photos"]
    assert [(p["id"], p["is_primary"]) for p in photos] == [(second["id"], True)]


async def test_hidden_cars_are_not_public(client: httpx.AsyncClient) -> None:
    owner = await login(client, "client1@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(status="draft"), headers=owner)).json()

    assert (await client.get(f"/api/v1/cars/{car['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/cars/{car['id']}", headers=owner)).status_code == 200


async def test_admin_endpoints_need_an_admin(client: httpx.AsyncClient) -> None:
    clients_token = await login(client, "client1@drivenow.test")
    admin = await login(client, "admin1@drivenow.test")
    assert (await client.get("/api/v1/admin/stats", headers=clients_token)).status_code == 403
    assert (await client.get("/api/v1/admin/stats")).status_code == 401
    assert (await client.get("/api/v1/admin/stats", headers=admin)).json()["users"] >= 10


async def test_bug_flag_turns_the_four_bugs_on(client: httpx.AsyncClient, bugs_on: None) -> None:
    owner = await login(client, "client5@drivenow.test")
    other = await login(client, "client6@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(daily_price=71.71), headers=owner)).json()

    found = await client.get("/api/v1/cars", params={"min_price": 71.71, "max_price": 71.71})
    assert found.json()["total"] == 0, "BUG-004 should hide a car priced exactly at max_price"

    start = date.today() + timedelta(days=8)
    first = {"car_id": car["id"], "start_date": str(start), "end_date": str(start + timedelta(days=1))}
    around = {
        **first,
        "start_date": str(start - timedelta(days=1)),
        "end_date": str(start + timedelta(days=3)),
    }
    await client.post("/api/v1/bookings", json=first, headers=other)
    overlap = await client.post("/api/v1/bookings", json=around, headers=other)
    assert overlap.status_code == 201, "BUG-002 should accept an enclosing booking"

    updated = await client.put(
        f"/api/v1/cars/{car['id']}", json=car_payload(daily_price=89.99), headers=owner
    )
    assert updated.json()["daily_price"] == 89.0, "BUG-001 should cut the price"

    deleted = await client.delete(f"/api/v1/cars/{car['id']}", headers=other)
    assert deleted.status_code == 204, "BUG-003 should let another client delete the car"


async def test_search_text_is_not_a_wildcard(client: httpx.AsyncClient) -> None:
    everything = await client.get("/api/v1/cars", params={"q": "%"})
    assert everything.json()["total"] == 0, "a % in the search must be a literal character"


async def test_city_filter_ignores_case_but_not_wildcards(client: httpx.AsyncClient) -> None:
    lower = (await client.get("/api/v1/cars", params={"city": "prishtina"})).json()["total"]
    exact = (await client.get("/api/v1/cars", params={"city": "Prishtina"})).json()["total"]
    wildcard = (await client.get("/api/v1/cars", params={"city": "P%"})).json()["total"]
    assert lower == exact > 0
    assert wildcard == 0


async def test_unsafe_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    safe = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    unsafe = await client.get("/health", headers={"X-Request-ID": "bad\nid"})
    assert safe.headers["X-Request-ID"] == "abc-123"
    assert unsafe.headers["X-Request-ID"] != "bad\nid"


async def test_oversized_request_is_refused_before_reading(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/cars", content=b"x", headers={"Content-Length": str(100 * 1024 * 1024)}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_booking_survives_a_bus_outage(
    client: httpx.AsyncClient, bus: MemoryEventBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await login(client, "client1@drivenow.test")
    renter = await login(client, "client2@drivenow.test")
    car = (await client.post("/api/v1/cars", json=car_payload(), headers=owner)).json()

    async def broken_publish(event: dict[str, object]) -> None:
        raise ConnectionError("bus down")

    monkeypatch.setattr(bus, "publish", broken_publish)
    start = date.today() + timedelta(days=20)
    booking = await client.post(
        "/api/v1/bookings",
        json={"car_id": car["id"], "start_date": str(start), "end_date": str(start + timedelta(days=1))},
        headers=renter,
    )
    assert booking.status_code == 201, "a saved booking must not turn into an error when the bus is down"
