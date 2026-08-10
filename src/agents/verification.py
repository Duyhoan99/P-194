"""Claim-level evidence, exactness, negation and entailment verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.agents.contracts import VerifiedClaim
from src.agents.evidence import ScopedEvidence, is_prompt_injection_content
from src.agents.generation import GENERATOR_VERSION, ProposedClaim


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    status: Literal["verified", "needs_verification", "unsupported", "invalid"]
    evidence_ids: tuple[str, ...]
    checks: dict[str, bool]
    reasons: tuple[str, ...]


def _normalized_statement(evidence: ScopedEvidence) -> str | None:
    value = evidence.item.normalized_value
    if isinstance(value, dict):
        for key in ("statement", "public_text", "answer"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    if isinstance(value, str):
        return value.strip()
    return None


def _verification_tokens(evidence: ScopedEvidence) -> list[str]:
    value = evidence.item.normalized_value
    if not isinstance(value, dict):
        return []
    explicit = value.get("required_tokens")
    if isinstance(explicit, list):
        return [str(token) for token in explicit if token is not None and str(token)]
    tokens: list[str] = []
    for key in (
        "value",
        "unit",
        "date",
        "effective_date",
        "from",
        "to",
        "from_value",
        "to_value",
        "medication",
        "dose",
        "state",
    ):
        item = value.get(key)
        if item is not None and not isinstance(item, (dict, list)):
            tokens.append(str(item))
    if evidence.item.source_time:
        tokens.append(evidence.item.source_time[:10])
    return tokens


def _preserves_negation(text: str, evidence: ScopedEvidence) -> bool:
    value = evidence.item.normalized_value
    if not isinstance(value, dict):
        return True
    assertion = str(value.get("assertion", "")).casefold()
    if assertion not in {"absent", "negated", "negative"}:
        return True
    lowered = text.casefold()
    return any(marker in lowered for marker in ("không", "chưa ghi nhận", "phủ định", "no ", "not "))


def verify_claim(
    proposed: ProposedClaim,
    evidence_by_id: dict[str, ScopedEvidence],
) -> tuple[VerifiedClaim | None, ClaimVerification]:
    matched = [evidence_by_id[item_id] for item_id in proposed.evidence_ids if item_id in evidence_by_id]
    evidence_exists = len(matched) == len(proposed.evidence_ids) and bool(matched)
    citations_exist = evidence_exists and all(item.item.citations for item in matched)
    no_injection = evidence_exists and all(not is_prompt_injection_content(item.item) for item in matched)
    statements = [_normalized_statement(item) for item in matched]
    entailment = bool(statements) and all(
        statement is not None and proposed.text.casefold() == statement.casefold() for statement in statements
    )
    exactness = evidence_exists and all(
        all(token.casefold() in proposed.text.casefold() for token in _verification_tokens(item)) for item in matched
    )
    negation = evidence_exists and all(_preserves_negation(proposed.text, item) for item in matched)
    checks = {
        "evidence_exists": evidence_exists,
        "citations_exist": citations_exist,
        "numeric_unit_date_exact": exactness,
        "negation_preserved": negation,
        "entailed": entailment,
        "prompt_injection_ignored": no_injection,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    if not all(checks.values()):
        status: Literal["unsupported", "invalid"] = (
            "unsupported" if not evidence_exists or not entailment else "invalid"
        )
        return None, ClaimVerification(
            claim_id=proposed.claim_id,
            status=status,
            evidence_ids=tuple(proposed.evidence_ids),
            checks=checks,
            reasons=reasons,
        )

    needs_verification = any(item.item.verification_status == "needs_verification" for item in matched)
    status = "needs_verification" if needs_verification else "verified"
    citations = []
    seen_citations: set[str] = set()
    for item in matched:
        for citation in item.item.citations:
            if citation.citation_id not in seen_citations:
                seen_citations.add(citation.citation_id)
                citations.append(citation)
    claim = VerifiedClaim(
        claim_id=proposed.claim_id,
        text=proposed.text,
        status=status,
        confidence="low" if needs_verification else "high",
        citations=citations,
        generator_version=GENERATOR_VERSION,
    )
    return claim, ClaimVerification(
        claim_id=proposed.claim_id,
        status=status,
        evidence_ids=tuple(proposed.evidence_ids),
        checks=checks,
        reasons=(),
    )


def verify_claims(
    proposed_claims: list[ProposedClaim],
    evidence_packet: list[ScopedEvidence],
) -> tuple[list[VerifiedClaim], list[ClaimVerification]]:
    evidence_by_id = {evidence.item.evidence_id: evidence for evidence in evidence_packet}
    public_claims: list[VerifiedClaim] = []
    results: list[ClaimVerification] = []
    for proposed in proposed_claims:
        claim, result = verify_claim(proposed, evidence_by_id)
        results.append(result)
        if claim is not None:
            public_claims.append(claim)
    return public_claims, results
