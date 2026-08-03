"""Access-aware orchestration for evidence-first clinical summary generation."""

from src.clinical.schemas import AccessContext, ClinicalQuery, EvidenceRecord
from src.clinical.service import ClinicalRetrievalService
from src.clinical.summary_generator import DeterministicDemoSummaryGenerator, SummaryGenerator
from src.clinical.summary_schemas import ClinicalSummaryDraft


class ClinicalSummaryService:
    """Retrieves only authorized evidence before creating a draft summary."""

    def __init__(
        self,
        retrieval_service: ClinicalRetrievalService,
        generator: SummaryGenerator | None = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._generator = generator or DeterministicDemoSummaryGenerator()

    def generate(self, context: AccessContext, query: ClinicalQuery) -> ClinicalSummaryDraft:
        evidence: list[EvidenceRecord] = []
        for response in self._responses(context, query):
            evidence.extend(response.records)
        draft = self._generator.generate(evidence)
        return draft.model_copy(
            update={
                "subject_id": query.subject_id,
                "hadm_id": query.hadm_id,
                "stay_id": query.stay_id,
                "trace_id": context.trace_id,
            }
        )

    def _responses(self, context: AccessContext, query: ClinicalQuery):
        return (
            self._retrieval_service.get_patient_overview(context, query),
            self._retrieval_service.get_encounter_timeline(context, query),
            self._retrieval_service.get_diagnoses_and_procedures(context, query),
            self._retrieval_service.get_laboratory_results(context, query),
            self._retrieval_service.get_microbiology_results(context, query),
            self._retrieval_service.get_icu_events(context, query),
        )
