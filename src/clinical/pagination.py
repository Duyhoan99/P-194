"""Bound, expiring cursors for clinical page boundaries."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

from src.clinical.errors import ClinicalScopeInvalid

_MAX_TOKEN_LENGTH = 4096


class CursorBinding(BaseModel):
    """The non-clinical query identity to which a cursor is bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    endpoint: str = Field(min_length=1, max_length=80)
    subject_id: int
    hadm_id: int | None = None
    stay_id: int | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None
    source_profile: str = Field(min_length=1, max_length=120)
    order_version: str = Field(min_length=1, max_length=32)


class CursorPosition(BaseModel):
    """The typed key of the last record returned on a page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_time: datetime | None = None
    domain: str = Field(min_length=1, max_length=80)
    source_key: str = Field(min_length=1, max_length=512)


class CursorPayload(BaseModel):
    """Signed cursor data; it contains no clinical measurements or notes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    binding: CursorBinding
    position: CursorPosition
    issued_at: datetime
    expires_at: datetime


def encode_cursor(payload: CursorPayload, secret: str, now: datetime | None = None) -> str:
    """Encode and sign a cursor using a canonical JSON representation."""

    _validate_secret(secret)
    current_time = now or datetime.now(UTC)
    _validate_aware(current_time)
    _validate_payload_times(payload)
    if payload.expires_at <= payload.issued_at:
        raise ClinicalScopeInvalid("Invalid clinical cursor")
    if current_time > payload.expires_at:
        raise ClinicalScopeInvalid("Invalid clinical cursor")

    body = _canonical_json(payload)
    body_token = _b64encode(body)
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    token = f"{body_token}.{_b64encode(signature)}"
    if len(token) > _MAX_TOKEN_LENGTH:
        raise ClinicalScopeInvalid("Invalid clinical cursor")
    return token


def decode_cursor(
    token: str,
    secret: str,
    expected: CursorBinding,
    now: datetime | None = None,
) -> CursorPayload:
    """Verify, decode, expire, and bind a cursor before any clinical query."""

    _validate_secret(secret)
    current_time = now or datetime.now(UTC)
    _validate_aware(current_time)
    if not token or len(token) > _MAX_TOKEN_LENGTH or token.count(".") != 1:
        raise ClinicalScopeInvalid("Invalid clinical cursor")

    body_token, signature_token = token.split(".", 1)
    try:
        body = _b64decode(body_token)
        supplied_signature = _b64decode(signature_token)
    except (ValueError, TypeError):
        raise ClinicalScopeInvalid("Invalid clinical cursor") from None

    expected_signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ClinicalScopeInvalid("Invalid clinical cursor")

    try:
        payload = CursorPayload.model_validate(json.loads(body))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ClinicalScopeInvalid("Invalid clinical cursor") from None

    _validate_payload_times(payload)
    if payload.binding != expected or current_time < payload.issued_at or current_time > payload.expires_at:
        raise ClinicalScopeInvalid("Invalid clinical cursor")
    return payload


def _canonical_json(payload: CursorPayload) -> bytes:
    return json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _validate_secret(secret: str) -> None:
    if not secret or len(secret) < 32:
        raise ClinicalScopeInvalid("Invalid clinical cursor")


def _validate_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ClinicalScopeInvalid("Invalid clinical cursor")


def _validate_payload_times(payload: CursorPayload) -> None:
    for value in (payload.issued_at, payload.expires_at, payload.position.event_time):
        if value is not None:
            _validate_aware(value)
    for value in (payload.binding.from_time, payload.binding.to_time):
        if value is not None:
            _validate_aware(value)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    if not value:
        raise ValueError("empty base64 value")
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
