from datetime import datetime

import pytest

from src.clinical.errors import ClinicalScopeInvalid
from src.clinical.pagination import (
    CursorBinding,
    CursorPayload,
    CursorPosition,
    decode_cursor,
    encode_cursor,
)


def aware(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.fixture
def secret() -> str:
    return "s" * 32


@pytest.fixture
def binding() -> CursorBinding:
    return CursorBinding(
        endpoint="labs",
        subject_id=101,
        hadm_id=None,
        stay_id=None,
        from_time=None,
        to_time=None,
        source_profile="mimic-iv-3.1",
        order_version="v1",
    )


@pytest.fixture
def payload(binding: CursorBinding) -> CursorPayload:
    return CursorPayload(
        binding=binding,
        position=CursorPosition(
            event_time=aware("2125-01-01T10:00:00Z"),
            domain="labevents",
            source_key="9001",
        ),
        issued_at=aware("2025-01-01T00:00:00Z"),
        expires_at=aware("2025-01-02T00:00:00Z"),
    )


def test_cursor_round_trip_and_binding(secret: str, binding: CursorBinding, payload: CursorPayload):
    now = aware("2025-01-01T12:00:00Z")
    token = encode_cursor(payload, secret, now=now)

    assert decode_cursor(token, secret, binding, now=now) == payload

    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token, secret, binding.model_copy(update={"subject_id": 202}), now=now)


def test_expired_or_modified_cursor_is_rejected(secret: str, binding: CursorBinding, payload: CursorPayload):
    token = encode_cursor(payload, secret, now=aware("2025-01-01T12:00:00Z"))

    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token + "x", secret, binding, now=aware("2025-01-01T12:00:00Z"))
    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(token, secret, binding, now=aware("2025-01-02T00:00:01Z"))


def test_cursor_rejects_naive_clock_and_empty_secret(binding: CursorBinding, payload: CursorPayload):
    with pytest.raises(ClinicalScopeInvalid):
        encode_cursor(payload, "")
    with pytest.raises(ClinicalScopeInvalid):
        decode_cursor(encode_cursor(payload, "s" * 32), "s" * 32, binding, now=datetime(2025, 1, 1))
