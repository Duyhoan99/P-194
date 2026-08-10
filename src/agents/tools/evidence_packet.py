"""Tools bound to one validated AgentRequest evidence packet.

No tool accepts a tenant or patient selected by model/user text.
"""

from __future__ import annotations

from src.agents.contracts import AgentRequest
from src.agents.evidence import ScopedEvidence, build_scoped_evidence, retrieve_evidence


class EvidencePacketTools:
    def __init__(self, request: AgentRequest) -> None:
        self._request = request
        self._packet = build_scoped_evidence(request)

    @property
    def packet(self) -> list[ScopedEvidence]:
        return list(self._packet)

    def structured(self, question: str | None, *, limit: int = 12) -> list[ScopedEvidence]:
        return retrieve_evidence(
            self._packet,
            route="structured",
            question=question,
            limit=limit,
        )

    def notes(self, question: str | None, *, limit: int = 12) -> list[ScopedEvidence]:
        return retrieve_evidence(self._packet, route="notes", question=question, limit=limit)

    def hybrid(self, question: str | None, *, limit: int = 12) -> list[ScopedEvidence]:
        return retrieve_evidence(self._packet, route="hybrid", question=question, limit=limit)
