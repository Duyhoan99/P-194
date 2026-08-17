"""Patient-scoped evidence packet adapters and bounded retrieval.

This module never opens source files or queries a database.  It consumes only
the already scoped ``AgentRequest`` supplied by the backend.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from src.agents.contracts import AgentRequest, Citation, EvidenceItem
from src.agents.retrieval.temporal import filter_temporal, filter_comparison_endpoints, TemporalQuery, _parse_time
from src.agents.retrieval.fusion import BaselineWeightedReranker
from src.agents.retrieval.tools import RetrievalCandidate, SafeTool


class EvidenceScopeError(ValueError):
    """Raised when an evidence identifier belongs to another patient/tenant."""


@dataclass(frozen=True)
class ScopedEvidence:
    item: EvidenceItem
    origin: Literal["structured", "note"]
    patient_id: str
    tenant_id: str
    record_status: str | None = None


_PATIENT_TOKEN = re.compile(r"PAT-?\d{3}", re.IGNORECASE)
_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "bỏ qua hướng dẫn",
    "bo qua huong dan",
    "system prompt",
    "developer message",
    "hãy mở hồ sơ",
)
_STOPWORDS = {
    "bệnh",
    "bệnh nhân",
    "bị",
    "bao",
    "bao nhiêu",
    "có",
    "cho",
    "các",
    "của",
    "được",
    "đang",
    "hồ sơ",
    "hiện",
    "gì",
    "kết",
    "kết quả",
    "không",
    "là",
    "lý",
    "mắc",
    "như",
    "nào",
    "nhiêu",
    "nhân",
    "những",
    "này",
    "người",
    "quả",
    "tại",
    "thế",
    "tôi",
    "the",
    "patient",
    "what",
}

_DOMAIN_TERMS = {
    "diagnosis": {"bệnh", "lý", "chẩn", "đoán", "tình", "trạng", "xác", "nhận", "ghi"},
    "medication": {"thuốc", "medication", "drug"},
    "lab": {"xét", "nghiệm", "kết", "quả", "lab"},
    "vital": {"sinh", "hiệu", "vital"},
}


def _patient_tokens(value: str) -> set[str]:
    return {token.upper().replace("PAT", "PAT-").replace("--", "-") for token in _PATIENT_TOKEN.findall(value)}


def _citation_identifiers(citation: Citation) -> Iterable[str]:
    yield citation.citation_id
    if hasattr(citation, "document_id"):
        yield citation.document_id
    if hasattr(citation, "resource_id"):
        yield citation.resource_id
    if hasattr(citation, "source_record_id"):
        yield citation.source_record_id


def _scope_tokens(item: EvidenceItem) -> set[str]:
    tokens = _patient_tokens(item.evidence_id)
    for citation in item.citations:
        for identifier in _citation_identifiers(citation):
            tokens.update(_patient_tokens(identifier))
    return tokens


def _record_status(payload: dict[str, Any], item: EvidenceItem) -> str | None:
    direct = payload.get("record_status") or payload.get("status")
    if direct:
        return str(direct).casefold().replace("_", "-")
    if isinstance(item.normalized_value, dict):
        nested = item.normalized_value.get("record_status") or item.normalized_value.get("status")
        if nested:
            return str(nested).casefold().replace("_", "-")
    return None


def _to_evidence_item(payload: dict[str, Any]) -> EvidenceItem:
    fields = EvidenceItem.model_fields
    contract_payload = {key: payload[key] for key in fields if key in payload}
    return EvidenceItem.model_validate(contract_payload)


def build_scoped_evidence(request: AgentRequest) -> list[ScopedEvidence]:
    """Validate the complete packet before retrieval and fail closed on leakage."""
    packet: list[ScopedEvidence] = []
    for raw in request.structured_facts:
        item = _to_evidence_item(raw)
        patient_id = str(raw.get("patient_id", request.patient_id))
        tenant_id = str(raw.get("tenant_id", request.tenant_id))
        packet.append(
            ScopedEvidence(
                item=item,
                origin="structured",
                patient_id=patient_id,
                tenant_id=tenant_id,
                record_status=_record_status(raw, item),
            )
        )
    packet.extend(
        ScopedEvidence(
            item=item,
            origin="note",
            patient_id=request.patient_id,
            tenant_id=request.tenant_id,
            record_status=_record_status({}, item),
        )
        for item in request.note_evidence
    )

    for scoped in packet:
        if scoped.patient_id != request.patient_id or scoped.tenant_id != request.tenant_id:
            raise EvidenceScopeError("Evidence packet scope does not match the locked request scope.")
        tokens = _scope_tokens(scoped.item)
        if tokens and tokens != {request.patient_id.upper()}:
            raise EvidenceScopeError("Evidence packet contains a foreign patient identifier.")
    return packet


def is_prompt_injection_content(item: EvidenceItem) -> bool:
    """Detect untrusted instructions for telemetry/tests; never execute them."""
    content = f"{item.fact_type} {item.source_value} {item.normalized_value}".casefold()
    return any(pattern in content for pattern in _INJECTION_PATTERNS)


def _search_text(item: EvidenceItem) -> str:
    snippets = " ".join(citation.snippet for citation in item.citations)
    return f"{item.fact_type} {item.normalized_value} {item.source_value} {snippets}".casefold()


def _terms(value: str) -> set[str]:
    return {
    "thế",
    "the",
    "patient",
    "what",
}


def _patient_tokens(value: str) -> set[str]:
    return {token.upper().replace("PAT", "PAT-").replace("--", "-") for token in _PATIENT_TOKEN.findall(value)}


def _citation_identifiers(citation: Citation) -> Iterable[str]:
    yield citation.citation_id
    if hasattr(citation, "document_id"):
        yield citation.document_id
    if hasattr(citation, "resource_id"):
        yield citation.resource_id
    if hasattr(citation, "source_record_id"):
        yield citation.source_record_id


def _scope_tokens(item: EvidenceItem) -> set[str]:
    tokens = _patient_tokens(item.evidence_id)
    for citation in item.citations:
        for identifier in _citation_identifiers(citation):
            tokens.update(_patient_tokens(identifier))
    return tokens


def _record_status(payload: dict[str, Any], item: EvidenceItem) -> str | None:
    direct = payload.get("record_status") or payload.get("status")
    if direct:
        return str(direct).casefold().replace("_", "-")
    if isinstance(item.normalized_value, dict):
        nested = item.normalized_value.get("record_status") or item.normalized_value.get("status")
        if nested:
            return str(nested).casefold().replace("_", "-")
    return None


def _to_evidence_item(payload: dict[str, Any]) -> EvidenceItem:
    fields = EvidenceItem.model_fields
    contract_payload = {key: payload[key] for key in fields if key in payload}
    return EvidenceItem.model_validate(contract_payload)


def build_scoped_evidence(request: AgentRequest) -> list[ScopedEvidence]:
    """Validate the complete packet before retrieval and fail closed on leakage."""
    packet: list[ScopedEvidence] = []
    for raw in request.structured_facts:
        item = _to_evidence_item(raw)
        patient_id = str(raw.get("patient_id", request.patient_id))
        tenant_id = str(raw.get("tenant_id", request.tenant_id))
        packet.append(
            ScopedEvidence(
                item=item,
                origin="structured",
                patient_id=patient_id,
                tenant_id=tenant_id,
                record_status=_record_status(raw, item),
            )
        )
    packet.extend(
        ScopedEvidence(
            item=item,
            origin="note",
            patient_id=request.patient_id,
            tenant_id=request.tenant_id,
            record_status=_record_status({}, item),
        )
        for item in request.note_evidence
    )

    for scoped in packet:
        if scoped.patient_id != request.patient_id or scoped.tenant_id != request.tenant_id:
            raise EvidenceScopeError("Evidence packet scope does not match the locked request scope.")
        tokens = _scope_tokens(scoped.item)
        if tokens and tokens != {request.patient_id.upper()}:
            raise EvidenceScopeError("Evidence packet contains a foreign patient identifier.")
    return packet


def is_prompt_injection_content(item: EvidenceItem) -> bool:
    """Detect untrusted instructions for telemetry/tests; never execute them."""
    content = f"{item.fact_type} {item.source_value} {item.normalized_value}".casefold()
    return any(pattern in content for pattern in _INJECTION_PATTERNS)


def _search_text(item: EvidenceItem) -> str:
    snippets = " ".join(citation.snippet for citation in item.citations)
    return f"{item.fact_type} {item.normalized_value} {item.source_value} {snippets}".casefold()


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w%/.+-]+", value.casefold(), flags=re.UNICODE)
        if len(token) > 1 and token not in _STOPWORDS
    }


def _plan_query_terms(question: str, plan: dict[str, Any] | None) -> set[str]:
    """Remove grammar and already-consumed domain concepts, leaving entity terms."""
    terms = _terms(question)
    if not plan:
        return terms
    for need in plan.get("needs", []):
        terms -= _DOMAIN_TERMS.get(str(need.get("domain", "")), set())
    return terms


def _is_packet_wide_plan(plan: dict[str, Any] | None) -> bool:
    if not plan:
        return False
    if plan.get("task_type") == "summary":
        return True
    return plan.get("task_type") == "clinical_question" and any(
        need.get("domain") == "all" and not need.get("entity")
        for need in plan.get("needs", [])
    )


def _is_concept_wide_plan(plan: dict[str, Any] | None) -> bool:
    """A domain request without an entity asks for the domain itself."""
    if not plan or plan.get("task_type") != "clinical_question":
        return False
    needs = plan.get("needs", [])
    return len(needs) == 1 and needs[0].get("domain") != "all" and not needs[0].get("entity")


def retrieve_evidence(
    packet: list[ScopedEvidence],
    *,
    route: Literal["structured", "notes", "hybrid", "not_allowed", "narrative", "temporal", "mixed"] | dict,
    question: str | None,
    limit: int = 12,
) -> list[ScopedEvidence]:
    """Filter, rank, and deduplicate using deterministic hybrid retrieval or RetrievalPlan."""
    if route == "not_allowed":
        return []
        
    # 1. Base candidates filtering
    candidates = [
        scoped
        for scoped in packet
        if scoped.record_status not in {"entered-in-error", "entered-inerror"}
    ]
    
    if not candidates:
        return []
        
    # Parse plan if provided as dict
    plan_dict = route if isinstance(route, dict) else None
    
    if plan_dict and not plan_dict.get("retrieval_required", True):
        return []

    wrapped_candidates = [RetrievalCandidate(c) for c in candidates]
    
    # 2. Strict Intent Filtering (if present)
    if plan_dict and plan_dict.get("strict_intent", "NONE") != "NONE":
        strict_intent = plan_dict["strict_intent"]
        if strict_intent == "PATIENT_OVERVIEW":
            diagnoses = [c for c in candidates if "diagnosis" in str(c.item.fact_type).casefold() or "bệnh" in str(c.item.normalized_value).casefold()]
            times = [c.item.source_time for c in candidates if c.item.source_time]
            if times:
                max_time = max(times)[:10]
                latest_metrics = [c for c in candidates if c.item.source_time and c.item.source_time.startswith(max_time) and str(c.item.fact_type).casefold() in {"lab", "vital"}]
                return diagnoses + latest_metrics
            return diagnoses
            
        elif strict_intent == "WARNING_STATUS":
            times = [c.item.source_time for c in candidates if c.item.source_time]
            if not times:
                return []
            max_time = max(times)[:10]
            warnings = []
            for c in candidates:
                if c.item.source_time and c.item.source_time.startswith(max_time):
                    status = str(c.record_status).upper()
                    if status in {"WARNING", "CRITICAL", "ABNORMAL", "HIGH", "LOW"}:
                        warnings.append(c)
                    else:
                        from src.clinical.guidelines import parse_and_evaluate_metric
                        stmt = str(c.item.normalized_value).casefold()
                        eval_res = parse_and_evaluate_metric(stmt, stmt)
                        if eval_res and eval_res.is_warning:
                            warnings.append(c)
            return warnings
            
        elif strict_intent == "LATEST_VISIT":
            times = [c.item.source_time for c in candidates if c.item.source_time]
            if not times:
                return []
            max_time = max(times)[:10]
            return [c for c in candidates if c.item.source_time and c.item.source_time.startswith(max_time)]
            
        elif strict_intent == "PREVIOUS_VISIT":
            times = sorted(list({c.item.source_time[:10] for c in candidates if c.item.source_time}), reverse=True)
            if len(times) < 2:
                return []
            prev_time = times[1]
            return [c for c in candidates if c.item.source_time and c.item.source_time.startswith(prev_time)]
            
        elif strict_intent == "SPECIFIC_TEST":
            entity = plan_dict.get("extracted_entity")
            if not entity:
                return []
            return [
                c for c in candidates 
                if entity in str(c.item.fact_type).casefold() 
                or entity in str(c.item.normalized_value).casefold() 
                or (isinstance(c.item.source_value, dict) and entity in str(c.item.source_value).casefold())
            ]
            
        elif strict_intent == "DISEASE":
            return [c for c in candidates if "diagnosis" in str(c.item.fact_type).casefold() or "bệnh" in str(c.item.normalized_value).casefold()]

    
    # Apply Safe Domain Filtering & Entity-specific Temporal Filtering
    if plan_dict and plan_dict.get("needs"):
        filtered_wrappers = []
        
        # Instantiate the safe tool abstraction
        tenant_id = wrapped_candidates[0].scoped.tenant_id if wrapped_candidates else ""
        patient_id = wrapped_candidates[0].scoped.patient_id if wrapped_candidates else ""
        safe_tool = SafeTool(tenant_id=tenant_id, patient_id=patient_id, preloaded_packet=wrapped_candidates)
        
        if _is_packet_wide_plan(plan_dict):
            filtered_wrappers = safe_tool.execute_summary(limit)
            
            # Apply temporal filtering even for summary/packet-wide plans
            need = plan_dict.get("needs", [{}])[0] if plan_dict.get("needs") else {}
            temporal_dict = need.get("temporal", {}) if isinstance(need, dict) else getattr(need, "temporal", {})
            if hasattr(temporal_dict, "model_dump"):
                temporal_dict = temporal_dict.model_dump()
            elif hasattr(temporal_dict, "__dict__"):
                temporal_dict = temporal_dict.__dict__
            
            intent = temporal_dict.get("intent", "none") if isinstance(temporal_dict, dict) else "none"
            if intent != "none" and filtered_wrappers:
                start_t = _parse_time(temporal_dict.get("start_time"))
                end_t = _parse_time(temporal_dict.get("end_time"))
                tk = limit  # For packet-wide, we want up to limit items from the latest encounter
                t_query = TemporalQuery(intent=intent, k=tk, start_time=start_t, end_time=end_t)
                dom_items = [c.scoped.item for c in filtered_wrappers]
                filtered_dom_items = filter_temporal(dom_items, t_query)
                filtered_ids = {id(it) for it in filtered_dom_items}
                if intent == "trend":
                    filtered_ids.update(
                        id(it) for it in dom_items
                        if "trend" in str(it.fact_type).casefold()
                    )
                filtered_wrappers = [c for c in filtered_wrappers if id(c.scoped.item) in filtered_ids]
        else:
            for need in plan_dict["needs"]:
                need_dict = need.model_dump() if hasattr(need, "model_dump") else (need if isinstance(need, dict) else need.__dict__)
                dom = need_dict.get("domain", "all")
                dom_cands = safe_tool.execute(dom)
                entity = need_dict.get("entity")
                if entity:
                    dom_cands = safe_tool.filter_entity(dom_cands, str(entity))
            
                temporal_dict = need_dict.get("temporal", {})
                intent = temporal_dict.get("intent", "none")
                if intent != "none" and dom_cands:
                    start_t = _parse_time(temporal_dict.get("start_time"))
                    end_t = _parse_time(temporal_dict.get("end_time"))
                    tk = limit if dom == "all" else (1 if intent in {"latest", "earliest", "previous"} else limit)
                    t_query = TemporalQuery(intent=intent, k=tk, start_time=start_t, end_time=end_t)
                    dom_items = [c.scoped.item for c in dom_cands]
                    filtered_dom_items = filter_temporal(dom_items, t_query)
                    filtered_ids = {id(it) for it in filtered_dom_items}
                    if intent == "trend":
                        filtered_ids.update(
                            id(it) for it in dom_items
                            if "trend" in str(it.fact_type).casefold()
                        )
                    dom_cands = [c for c in dom_cands if id(c.scoped.item) in filtered_ids]
                    if intent == "trend" and plan_dict.get("comparison_required"):
                        endpoint_items = filter_comparison_endpoints(
                            [c.scoped.item for c in dom_cands],
                            relative_months=temporal_dict.get("relative_months"),
                        )
                        if endpoint_items:
                            endpoint_ids = {id(item) for item in endpoint_items}
                            dom_cands = [c for c in dom_cands if id(c.scoped.item) in endpoint_ids]
                    
                filtered_wrappers.extend(dom_cands)
            
            
        # Deduplicate
        seen_ids = set()
        wrapped_candidates = []
        for c in filtered_wrappers:
            if c.evidence_id not in seen_ids:
                seen_ids.add(c.evidence_id)
                wrapped_candidates.append(c)
    elif route == "temporal" and question:
        q_lower = question.lower()
        intent = "trend"
        if "latest" in q_lower or "gần nhất" in q_lower:
            intent = "latest"
        elif "earliest" in q_lower or "cũ nhất" in q_lower:
            intent = "earliest"
        elif "trước đó" in q_lower or "lần trước" in q_lower:
            intent = "previous"
            
        tk = 1 if intent in {"latest", "earliest", "previous"} else limit
        t_query = TemporalQuery(intent=intent, k=tk)
        items = [c.scoped.item for c in wrapped_candidates]
        filtered_items = filter_temporal(items, t_query)
        filtered_ids = {id(it) for it in filtered_items}
        wrapped_candidates = [c for c in wrapped_candidates if id(c.scoped.item) in filtered_ids]

    if not wrapped_candidates:
        return []

    # Phase 2: Semantic Retrieval for relevant routes
    use_semantic = True
    if plan_dict:
        use_semantic = plan_dict.get("use_semantic", True)
    elif route not in {"narrative", "hybrid", "mixed"}:
        use_semantic = False
        
    if use_semantic and question:
        from src.agents.retrieval.vector import SemanticRetriever
        sem_retriever = SemanticRetriever()
        
        if wrapped_candidates:
            first_scoped = wrapped_candidates[0].scoped
            tenant_id = first_scoped.tenant_id
            patient_id = first_scoped.patient_id
            
            sem_scores = sem_retriever.retrieve(tenant_id, patient_id, question, k=limit)
            
            for cand in wrapped_candidates:
                ev_id_str = str(cand.evidence_id)
                if ev_id_str in sem_scores:
                    cand.semantic_score = sem_scores[ev_id_str]

    # 5. Hybrid Reranking
    reranker = BaselineWeightedReranker()
    ranked_wrappers = reranker.rerank(question or "", wrapped_candidates, k=limit)
    
    selected = []
    seen = set()
    query_terms = _plan_query_terms(question or "", plan_dict)
    for item in ranked_wrappers:
        if item.evidence_id in seen:
            continue
            
        # Enforce relevance filtering if required by the route or plan
        require_relevance = True
        if plan_dict:
            if _is_packet_wide_plan(plan_dict) or _is_concept_wide_plan(plan_dict):
                require_relevance = False
            # If the plan explicitly disables BOTH lexical and semantic, we don't require relevance (e.g. for summaries)
            elif not plan_dict.get("use_lexical", True) and not plan_dict.get("use_semantic", True):
                require_relevance = False
                
        if require_relevance and question:
            has_lexical = len(query_terms & _terms(_search_text(item.scoped.item))) > 0 if query_terms else True
            if not has_lexical and getattr(item, "semantic_score", 0.0) == 0.0:
                continue

        seen.add(item.evidence_id)
        selected.append(item.scoped)

    return selected
