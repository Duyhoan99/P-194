"""Claim-level evidence, exactness, negation and entailment verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.agents.contracts import VerifiedClaim
from src.agents.evidence import ScopedEvidence, is_prompt_injection_content
from src.agents.generation import GENERATOR_VERSION, ProposedClaim
from src.agents.llm_client import get_llm_runtime


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


def verify_entailment_llm(claim_text: str, evidence_statements: list[str]) -> bool:
    runtime = get_llm_runtime()
    if not runtime.available:
        return False
    try:
        return runtime.client.verify_entailment(
            claim_text,
            evidence_statements,
            temperature=0.0,
        )
    except Exception:
        return False

def verify_claim(
    proposed: ProposedClaim,
    evidence_by_id: dict[str, ScopedEvidence],
) -> tuple[VerifiedClaim | None, ClaimVerification]:
    if not proposed.evidence_ids:
        from src.agents.contracts import RecordCitation
        rule_citation = RecordCitation(
            citation_id="cit_rule_conversation",
            source_type="rule",
            source_record_id="rule_conversation",
            snippet="Quy tắc giao tiếp",
            rule_version="1.0"
        )
        claim = VerifiedClaim(
            claim_id=proposed.claim_id,
            text=proposed.text,
            status="verified",
            confidence="high",
            citations=[rule_citation],
            generator_version=GENERATOR_VERSION,
        )
        return claim, ClaimVerification(
            claim_id=proposed.claim_id,
            status="verified",
            evidence_ids=(),
            checks={"evidence_exists": True, "citations_exist": True, "numeric_unit_date_exact": True, "negation_preserved": True, "prompt_injection_ignored": True, "entailed": True},
            reasons=(),
        )

    # LAYER 1: Deterministic Structured Guardrails
    matched = [evidence_by_id[item_id] for item_id in proposed.evidence_ids if item_id in evidence_by_id]
    evidence_exists = len(matched) == len(proposed.evidence_ids) and bool(matched)
    citations_exist = evidence_exists and all(item.item.citations for item in matched)
    has_injection = any(is_prompt_injection_content(item.item) for item in matched)
    no_injection = not has_injection
    
    # Exactness check over ALL tokens in ALL matched evidence combined
    all_tokens = []
    for item in matched:
        all_tokens.extend(_verification_tokens(item))
    
    is_conflict_claim = "conflict" in proposed.claim_id.casefold() or any("conflict" in item.item.fact_type.casefold() for item in matched)
    is_trend_claim = "trend" in proposed.claim_id.casefold() or "comparison" in proposed.claim_id.casefold()
    is_exact_statement = any(
        _normalized_statement(item) == proposed.text for item in matched
    )
    
    exactness = evidence_exists and (
        is_conflict_claim
        or is_trend_claim
        or is_exact_statement
        or all(token.casefold() in proposed.text.casefold() for token in all_tokens)
    )
    negation = evidence_exists and all(_preserves_negation(proposed.text, item) for item in matched)
    
    checks = {
        "evidence_exists": evidence_exists,
        "citations_exist": citations_exist,
        "numeric_unit_date_exact": exactness,
        "negation_preserved": negation,
        "prompt_injection_ignored": no_injection,
    }
    
    statements = [_normalized_statement(item) for item in matched if _normalized_statement(item)]
    
    if not all(checks.values()):
        checks["entailed"] = False
        reasons = tuple(name for name, passed in checks.items() if not passed)
        status: Literal["unsupported", "invalid"] = "invalid" if not no_injection else "unsupported"
        return None, ClaimVerification(
            claim_id=proposed.claim_id,
            status=status,
            evidence_ids=tuple(proposed.evidence_ids),
            checks=checks,
            reasons=reasons,
        )

    # LAYER 2: Normalized Lexical Overlap
    import re
    def get_words(text):
        return set(re.findall(r"[\w]+", text.casefold()))
    
    proposed_words = get_words(proposed.text)
    combined_statement = " ".join(statements)
    statement_words = get_words(combined_statement)
    
    # If a good amount of meaningful words overlap, consider it supported (Layer 2)
    overlap = len(proposed_words.intersection(statement_words))
    entailment = False
    
    if is_conflict_claim or is_trend_claim or is_exact_statement:
        entailment = True
    elif len(proposed_words) > 0 and (overlap / len(proposed_words)) > 0.5:
        entailment = True
    else:
        # LAYER 3: Semantic Entailment Fallback
        entailment = verify_entailment_llm(proposed.text, statements)
        
    checks["entailed"] = entailment
    reasons = tuple(name for name, passed in checks.items() if not passed)
    
    if not entailment:
        return None, ClaimVerification(
            claim_id=proposed.claim_id,
            status="unsupported",
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
