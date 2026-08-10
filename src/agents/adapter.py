"""Stable C2/C3 adapter boundary for backend-supplied AgentRequest payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.agents.contracts import AgentRequest
from src.agents.state import RuntimeScope


class AgentRequestAdapter:
    """Validate a backend/fixture payload without changing the public contract."""

    def adapt(self, payload: Mapping[str, Any], *, runtime_scope: RuntimeScope) -> AgentRequest:
        request = AgentRequest.model_validate(dict(payload))
        if (
            request.tenant_id != runtime_scope["tenant_id"]
            or request.patient_id != runtime_scope["patient_id"]
            or request.request_id != runtime_scope["request_id"]
        ):
            raise ValueError("Backend payload does not match locked runtime scope.")
        return request
