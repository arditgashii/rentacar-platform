import re

import httpx


async def _csrf(client: httpx.AsyncClient, path: str) -> str:
    page = await client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert match, f"no CSRF token on {path}"
    return match.group(1)


async def test_pages_render(client: httpx.AsyncClient) -> None:
    for path in ("/", "/cars", "/cars?city=Peja&sort=price_asc", "/login", "/register"):
        response = await client.get(path)
        assert response.status_code == 200, path
        assert "DriveNow" in response.text


async def test_unknown_page_is_an_html_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/cars/999999")
    assert response.status_code == 404
    assert 'data-testid="error-page"' in response.text


async def test_private_pages_redirect_to_login(client: httpx.AsyncClient) -> None:
    response = await client.get("/my/listings")
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fmy%2Flistings"


async def test_form_without_csrf_token_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/login", data={"email": "client1@drivenow.test", "password": "DriveNow!2026"}
    )
    assert response.status_code == 400


async def test_login_sets_the_session_cookie(client: httpx.AsyncClient) -> None:
    token = await _csrf(client, "/login")
    response = await client.post(
        "/login",
        data={"email": "admin1@drivenow.test", "password": "DriveNow!2026", "csrf_token": token},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert "access_token" in response.cookies

    admin_page = await client.get("/admin")
    assert 'data-testid="admin-stats"' in admin_page.text


async def test_login_never_redirects_to_another_site(client: httpx.AsyncClient) -> None:
    token = await _csrf(client, "/login")
    response = await client.post(
        "/login",
        data={
            "email": "client1@drivenow.test",
            "password": "DriveNow!2026",
            "csrf_token": token,
            "next": "//evil.example.com",
        },
    )
    assert response.headers["location"] == "/cars"


async def test_private_pages_are_not_cached(client: httpx.AsyncClient) -> None:
    token = await _csrf(client, "/login")
    await client.post(
        "/login", data={"email": "client1@drivenow.test", "password": "DriveNow!2026", "csrf_token": token}
    )
    private = await client.get("/my/listings")
    assert private.headers["cache-control"] == "no-store", "Back after logout would show this page"
    client.cookies.clear()
    public = await client.get("/cars")
    assert "cache-control" not in public.headers
