import pytest

from src.config import get_settings


@pytest.mark.asyncio
async def test_demo_login_sets_http_only_signed_session_cookie(client, monkeypatch):
    """Dropping cookie authentication would let callers forge clinical identities with headers."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    get_settings.cache_clear()

    response = await client.post(
        "/api/v1/auth/demo-login",
        json={"username": "doctor-1", "password": "demo"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert "demo_session" in response.cookies
    assert "HttpOnly" in response.headers["set-cookie"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_demo_logout_clears_session_cookie(client, monkeypatch):
    """Leaving a session cookie intact after logout would retain clinical access."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    get_settings.cache_clear()
    await client.post(
        "/api/v1/auth/demo-login",
        json={"username": "doctor-1", "password": "demo"},
    )

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert "demo_session=\"\"" in response.headers["set-cookie"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_demo_login_is_rejected_in_production(client, monkeypatch):
    """Enabling demo credentials in production would bypass organization authentication."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    get_settings.cache_clear()

    response = await client.post(
        "/api/v1/auth/demo-login",
        json={"username": "doctor-1", "password": "demo"},
    )

    assert response.status_code == 503
    get_settings.cache_clear()
