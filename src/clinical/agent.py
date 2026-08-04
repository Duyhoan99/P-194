"""LangGraph orchestration for evidence-grounded clinical summary drafts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import NAMESPACE_URL, uuid5

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from src.clinical.claim_validator import ClaimValidator
from src.clinical.errors import ClinicalAccessDenied, ClinicalAgentUnavailable, ReviewPolicyError
from src.clinical.schemas import AccessContext, ClinicalQuery, ClinicalResponse, EvidenceRecord
from src.clinical.service import ClinicalRetrievalService
from src.clinical.summary_generator import SummaryGenerator
from src.clinical.summary_schemas import SUMMARY_SECTIONS, ClinicalSummaryDraft, ValidationReport


class AgentState(TypedDict, total=False):
    context: AccessContext
    query: ClinicalQuery
    responses: tuple[ClinicalResponse, ...]
    evidence: list[EvidenceRecord]
    draft: ClinicalSummaryDraft
    validation: ValidationReport


StructuredDraftCaller = Any


@dataclass(frozen=True)
class ClinicalAgentResult:
    responses: tuple[ClinicalResponse, ...]
    evidence: list[EvidenceRecord]
    draft: ClinicalSummaryDraft

_SYSTEM_PROMPT = """You are an evidence-only clinical summarization assistant for a synthetic local demo.
Use only the supplied evidence records. Do not diagnose, recommend treatment, infer facts,
or invent missing values. Every clinical claim must have one or more citation_ids that exactly
match supplied evidence source_row_key values. Include the exact supported numeric value, unit,
and ISO timestamp in laboratory claims. Do not output treatment directives, diagnoses, clinical
opinions, chain-of-thought, prompts, or explanations outside the requested structure. Return only
the requested ClinicalSummaryDraft structure.
The server will overwrite identity, scope, status, and trace fields after validation."""


def build_agent_context(evidence: list[EvidenceRecord]) -> str:
    """Serialize bounded evidence context without adding prompt or logging side effects."""
    payload = [
        {
            "record_type": record.record_type,
            "data": record.data,
            "lineage": record.lineage.model_dump(mode="json"),
            "related_sources": [source.model_dump(mode="json") for source in record.related_sources],
        }
        for record in evidence
    ]
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)


class ClinicalAgent:
    """Runs access-aware retrieval, structured LLM generation, and citation validation."""

    def __init__(
        self,
        retrieval_service: ClinicalRetrievalService,
        structured_llm: StructuredDraftCaller,
        *,
        validator: ClaimValidator | None = None,
        fallback_generator: SummaryGenerator | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._structured_llm = structured_llm
        self._validator = validator or ClaimValidator()
        self._fallback_generator = fallback_generator
        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("generate", self._generate_node)
        graph.add_node("validate", self._validate_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "validate")
        graph.add_edge("validate", "finalize")
        graph.add_edge("finalize", END)
        self._graph = graph.compile()

    def generate(self, context: AccessContext, query: ClinicalQuery) -> ClinicalSummaryDraft:
        """Generate a validated draft or fail closed without returning partial output."""
        return self.run(context, query).draft

    def run(self, context: AccessContext, query: ClinicalQuery) -> ClinicalAgentResult:
        """Run the graph and retain retrieval metadata for the summary service boundary."""
        try:
            result = self._graph.invoke({"context": context, "query": query})
        except (ClinicalAccessDenied, ClinicalAgentUnavailable, ReviewPolicyError):
            raise
        except Exception as error:
            raise ClinicalAgentUnavailable("Structured summary generation failed safely.") from error
        draft = result.get("draft")
        responses = result.get("responses")
        evidence = result.get("evidence")
        if not isinstance(draft, ClinicalSummaryDraft) or not isinstance(responses, tuple) or not isinstance(evidence, list):
            raise ClinicalAgentUnavailable("Structured summary generation failed safely.")
        return ClinicalAgentResult(responses=responses, evidence=evidence, draft=draft)

    def _retrieve_node(self, state: AgentState) -> dict[str, object]:
        context = state["context"]
        query = state["query"]
        responses = (
            self._retrieval_service.get_patient_overview(context, query),
            self._retrieval_service.get_encounter_timeline(context, query),
            self._retrieval_service.get_diagnoses_and_procedures(context, query),
            self._retrieval_service.get_laboratory_results(context, query),
            self._retrieval_service.get_microbiology_results(context, query),
            self._retrieval_service.get_medications(context, query),
            self._retrieval_service.get_patient_metrics(context, query),
            self._retrieval_service.get_icu_events(context, query),
        )
        if any(response.status == "DENIED" for response in responses):
            raise ClinicalAccessDenied
        return {
            "responses": responses,
            "evidence": [record for response in responses for record in response.records],
        }

    def _generate_node(self, state: AgentState) -> dict[str, ClinicalSummaryDraft]:
        query = state["query"]
        evidence = state["evidence"]
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    {
                        "requested_scope": query.model_dump(mode="json"),
                        "evidence": json.loads(build_agent_context(evidence)),
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            ),
        ]
        try:
            raw_draft = self._structured_llm.invoke(messages)
            draft = raw_draft if isinstance(raw_draft, ClinicalSummaryDraft) else ClinicalSummaryDraft.model_validate(raw_draft)
        except Exception as error:
            if self._fallback_generator is None:
                raise ClinicalAgentUnavailable("Structured summary generation failed safely.") from error
            try:
                draft = self._fallback_generator.generate(evidence)
            except Exception as fallback_error:
                raise ClinicalAgentUnavailable("Structured summary generation failed safely.") from fallback_error
            draft = draft.model_copy(
                update={
                    "limitations": [
                        *draft.limitations,
                        "Structured AI output was unavailable; this evidence-only draft was generated without model prose.",
                    ]
                }
            )
        return {"draft": draft}

    def _validate_node(self, state: AgentState) -> dict[str, ValidationReport]:
        draft = state["draft"]
        evidence = state["evidence"]
        if any(claim.status != "VALID" for claims in draft.sections.values() for claim in claims):
            raise ReviewPolicyError("Agent output contains unsupported clinical claims.")
        report = self._validator.validate(draft, evidence)
        if not report.valid:
            raise ReviewPolicyError("Agent output requires evidence-backed citations.")
        evidence_ids = {record.lineage.source_row_key for record in evidence}
        if any(source_id not in evidence_ids for conflict in draft.conflicts for source_id in conflict.evidence_ids):
            raise ReviewPolicyError("Agent output contains an unsupported conflict reference.")
        return {"validation": report}

    def _finalize_node(self, state: AgentState) -> dict[str, ClinicalSummaryDraft]:
        context = state["context"]
        query = state["query"]
        draft = state["draft"]
        responses = state["responses"]
        evidence = state["evidence"]
        evidence_key = "|".join(sorted(record.lineage.source_row_key for record in evidence)) or "empty"
        scope_key = f"subject={query.subject_id}|hadm={query.hadm_id}|stay={query.stay_id}"
        warnings = list(dict.fromkeys([*draft.warnings, *(item for response in responses for item in response.warnings)]))
        limitations = list(dict.fromkeys([*draft.limitations, *(item for response in responses for item in response.limitations)]))
        sections = {section: draft.sections.get(section, []) for section in SUMMARY_SECTIONS}
        return {
            "draft": draft.model_copy(
                update={
                    "summary_id": uuid5(NAMESPACE_URL, f"clinical-summary:{scope_key}|evidence={evidence_key}"),
                    "subject_id": query.subject_id,
                    "hadm_id": query.hadm_id,
                    "stay_id": query.stay_id,
                    "status": "DRAFT",
                    "sections": sections,
                    "warnings": warnings,
                    "limitations": limitations,
                    "trace_id": context.trace_id,
                }
            )
        }
