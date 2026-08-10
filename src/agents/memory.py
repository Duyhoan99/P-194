"""Approved-only patient memory projection policy.

Persistence belongs to the backend owner.  This module only defines the
whitelist and validates a proposed projection.
"""

from __future__ import annotations

from typing import Any

from src.agents.contracts import ReviewSection

MEMORY_SECTION_ALLOWLIST = {
    "active_conditions",
    "current_medications",
    "changes_to_review",
}


class MemoryPolicyError(ValueError):
    pass


def project_approved_memory(
    *,
    review_status: str,
    patient_id: str,
    review_version_id: str,
    approved_by: str | None,
    approved_at: str | None,
    sections: list[ReviewSection],
) -> dict[str, Any]:
    """Return a minimal versioned projection or fail closed.

    Only verified, cited claims from an approved review are eligible.  Draft,
    generated, stale and ``needs_verification`` content never enters memory.
    """
    if review_status != "approved":
        raise MemoryPolicyError("Patient memory can only be projected from an approved review.")
    if not approved_by or not approved_at:
        raise MemoryPolicyError("Approved memory requires approver and approval time.")
    items: list[dict[str, Any]] = []
    for section in sections:
        if section.section_code not in MEMORY_SECTION_ALLOWLIST:
            continue
        for claim in section.claims:
            if claim.status != "verified" or not claim.citations:
                continue
            items.append(
                {
                    "section_code": section.section_code,
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "citation_ids": [citation.citation_id for citation in claim.citations],
                }
            )
    return {
        "patient_id": patient_id,
        "source_review_version_id": review_version_id,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "items": items,
    }
