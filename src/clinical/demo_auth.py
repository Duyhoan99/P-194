"""Signed development/test-only sessions for the clinical demo."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Final

# pyrefly: ignore [missing-import]
from fastapi import Request

from src.clinical.errors import ClinicalAuthNotConfigured
from src.clinical.schemas import AccessContext
from src.config import Settings, get_settings

DEMO_SESSION_COOKIE: Final = "demo_session"
_DEMO_PASSWORD: Final = "demo"
_CONTRACT_TEST_PASSWORD: Final = "demo-password"


def authenticate_demo_credentials(username: str, password: str) -> str:
    """Validate fixed local credentials without exposing account details."""
    from src.clinical.operations import operational_store

    target_user = username
    if username in {"doctor@example.test", "usr_doctor_demo"}:
        target_user = "usr_doctor_demo"
    elif "@" in username:
        target_user = username.split("@")[0]

    valid_passwords = {_DEMO_PASSWORD, _CONTRACT_TEST_PASSWORD}
    if operational_store.session_identity(target_user) is None or password not in valid_passwords:
        raise ClinicalAuthNotConfigured("Demo credentials are invalid")
    return target_user


class DemoSessionProvider:
    """Authenticates signed demo sessions and never trusts request identity headers."""

    def authenticate(self, request: Request) -> AccessContext:
        settings = get_settings()
        _require_demo_environment(settings)
        token = request.cookies.get(DEMO_SESSION_COOKIE)
        if token is None:
            raise ClinicalAuthNotConfigured("A demo clinical session is required")
        payload = _verify_session(token, settings)
        user_id = payload.get("user_id")
        if not isinstance(user_id, str):
            raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
        from src.clinical.operations import operational_store

        identity = operational_store.session_identity(user_id)
        if identity is None:
            raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
        role, assigned_patient_ids = identity
        return AccessContext(
            user_id=user_id,
            role=role,
            assigned_patient_ids=assigned_patient_ids,
            trace_id=getattr(request.state, "clinical_trace_id"),
        )


def create_demo_session(username: str, settings: Settings | None = None) -> tuple[str, int]:
    """Create a canonical, signed session token and its cookie lifetime."""
    configured = settings or get_settings()
    _require_demo_environment(configured)
    from src.clinical.operations import operational_store

    if operational_store.session_identity(username) is None:
        raise ClinicalAuthNotConfigured("Demo credentials are invalid")
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=configured.session_ttl_seconds)
    payload = {
        "expires_at": int(expires_at.timestamp()),
        "issued_at": int(now.timestamp()),
        "user_id": username,
    }
    body = _canonical_json(payload)
    signature = hmac.new(_session_secret(configured), body, hashlib.sha256).digest()
    return f"{_b64encode(body)}.{_b64encode(signature)}", configured.session_ttl_seconds


def _verify_session(token: str, settings: Settings) -> dict[str, object]:
    if token.count(".") != 1 or len(token) > 4096:
        raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
    encoded_body, encoded_signature = token.split(".")
    try:
        body = _b64decode(encoded_body)
        signature = _b64decode(encoded_signature)
        payload = json.loads(body)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise ClinicalAuthNotConfigured("Demo clinical session is invalid") from None
    if not isinstance(payload, dict) or _canonical_json(payload) != body:
        raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
    expected = hmac.new(_session_secret(settings), body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
    expires_at = payload.get("expires_at")
    issued_at = payload.get("issued_at")
    now = int(datetime.now(UTC).timestamp())
    if not isinstance(expires_at, int) or not isinstance(issued_at, int) or issued_at > now or expires_at <= now:
        raise ClinicalAuthNotConfigured("Demo clinical session is invalid")
    return payload


def _require_demo_environment(settings: Settings) -> None:
    if settings.app_env not in {"development", "test"}:
        raise ClinicalAuthNotConfigured("Demo authentication is disabled")


def _session_secret(settings: Settings) -> bytes:
    secret = settings.session_secret.encode("utf-8")
    if len(secret) < 32:
        raise ClinicalAuthNotConfigured("A demo session secret is required")
    return secret


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
