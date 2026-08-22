---
title: "State Management"
description: "State contract hiện tại của Clinical Review Agent"
weight: 1
---

## State đang dùng

`src/agents/state.py` định nghĩa hai state:

- `AgentState`: graph hội thoại cơ bản.
- `ClinicalReviewState`: graph review/ask-chart có patient scope và evidence.

```python
class ClinicalReviewState(TypedDict, total=False):
    request: AgentRequest
    runtime_scope: RuntimeScope
    question_type: QuestionType
    evidence_packet: list[ScopedEvidence]
    retrieved_evidence: list[ScopedEvidence]
    proposed_claims: list[ProposedClaim]
    claims: list[VerifiedClaim]
    unsupported_claims: list[VerifiedClaim]
    conflicts: list[dict]
    verification_results: list[ClaimVerification]
    status: Literal[
        "running", "answered", "not_found",
        "conflicting", "not_allowed", "error",
    ]
    errors: list[AgentError]
    public_response: AgentResult
```

## Ràng buộc

- `runtime_scope` luôn chứa `tenant_id`, `patient_id`, `request_id` do server cấp.
- Evidence đi qua canonicalizer FHIR/PDF trước khi vào graph.
- Claim `verified` phải có citation hợp lệ; claim không được hỗ trợ chuyển sang `unsupported_claims`.
- Graph không trả internal state, prompt, secret hoặc raw document ra API.
- `AgentResult` là public contract duy nhất cho review generation và ask-chart.
