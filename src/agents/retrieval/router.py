from typing import Literal, Any
import re
from pydantic import BaseModel, Field
from src.agents.llm_client import get_llm_runtime
from src.agents.retrieval.concepts import resolve_concept

QueryRoute = Literal["STRUCTURED", "NARRATIVE", "MIXED", "TEMPORAL", "SUMMARY", "OUT_OF_SCOPE", "CONVERSATION"]
StrictIntent = Literal["PATIENT_OVERVIEW", "WARNING_STATUS", "LATEST_VISIT", "PREVIOUS_VISIT", "DISEASE", "LAB_RESULT", "VITAL_SIGN", "MEDICATION", "VISIT", "HISTORY", "COMPARISON", "SPECIFIC_TEST", "UNKNOWN", "NONE"]

_SUMMARY_INTENT_MARKERS = (
    "tóm tắt",
    "tổng hợp",
    "tổng quan",
    "summary",
    "summarize",
    "overview",
)

_CONVERSATION_MARKERS = {
    "xin chào", "chào", "hello", "hi", "cảm ơn", "thanks", "thank you",
    "tạm biệt", "hẹn gặp lại", "bye", "goodbye", "ok", "okay",
}

_CONFLICT_INTENT_MARKERS = ("conflict", "mâu thuẫn", "xung đột", "không nhất quán", "trái ngược")
_COMPARISON_MARKERS = ("so sánh", "đối chiếu", "so với", "khác biệt", "compare", "versus", " vs ")
_TREND_MARKERS = (
    "thay đổi", "theo thời gian", "diễn biến", "diễn tiến", "xu hướng", "trend",
    "đổi trạng thái", "duy trì", "ngừng",
)
_LAB_CONCEPT_MARKERS = ("cận lâm sàng", "xét nghiệm", "chỉ số", "lab")
_MEDICATION_ENTITIES = {"Metformin", "Amlodipine"}
_CLINICAL_CONTEXT_MARKERS = (
    "hồ sơ", "bệnh án", "sức khỏe", "lâm sàng", "bệnh nhân", "người bệnh",
    "ca bệnh", "ca này", "điều trị", "triệu chứng", "thủ thuật", "lượt khám", "chức năng",
)
_LOW_INFORMATION_TERMS = {"thế", "nào", "rồi", "sao", "vậy", "à", "ừ", "ờ", "hả"}


def _extract_entity(question: str) -> str | None:
    concept = resolve_concept(question)
    return concept.canonical if concept else None


def _has_clinical_signal(question: str) -> bool:
    domain_markers = (
        "bệnh", "chẩn đoán", "thuốc", "medication", "xét nghiệm", "lab",
        "kết quả", "huyết áp", "nhịp tim", "mạch", "cân nặng", "ghi chú", "note",
    )
    return _extract_entity(question) is not None or any(
        marker in question for marker in domain_markers + _CLINICAL_CONTEXT_MARKERS
    )


def _is_low_information(question: str) -> bool:
    tokens = set(re.findall(r"\w+", question, flags=re.UNICODE))
    return not tokens or (not _has_clinical_signal(question) and tokens <= _LOW_INFORMATION_TERMS)


def _relative_months(question: str) -> int | None:
    if "nửa năm" in question or "half year" in question:
        return 6
    match = re.search(r"(\d+)\s*(?:tháng|month)s?", question)
    if match:
        return int(match.group(1))
    number_words = {
        "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6,
        "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
    }
    for word, value in number_words.items():
        if re.search(fr"\b{word}\s+tháng\b", question):
            return value
    return None

class TemporalIntent(BaseModel):
    intent: Literal["latest", "earliest", "previous", "before", "after", "between", "trend", "none"] = "none"
    start_time: str | None = None
    end_time: str | None = None
    relative_months: int | None = Field(default=None, ge=1, le=120)

class DomainNeed(BaseModel):
    domain: Literal["diagnosis", "medication", "lab", "vital", "encounter", "note", "procedure", "symptom", "all"]
    entity: str | None = None
    temporal: TemporalIntent = Field(default_factory=TemporalIntent)

class RetrievalPlan(BaseModel):
    task_type: Literal["conversation", "clarification", "clinical_question", "summary", "conflict_check", "out_of_scope"]
    needs: list[DomainNeed] = Field(default_factory=list)
    use_structured: bool = True
    use_semantic: bool = True
    use_lexical: bool = True
    retrieval_required: bool = True
    comparison_required: bool = False
    strict_intent: StrictIntent = "NONE"
    extracted_entity: str | None = None
    
    @property
    def route(self) -> str:
        """Helper to map back to legacy QueryRoute for compatibility, or return a custom one."""
        if self.task_type in {"conversation", "clarification"}: return "CONVERSATION"
        if self.task_type == "summary": return "SUMMARY"
        if self.task_type == "conflict_check": return "MIXED"
        if self.task_type == "out_of_scope": return "OUT_OF_SCOPE"
        # For clinical_question, figure out the best route mapping for legacy evidence.py
        if any(n.temporal.intent != "none" for n in self.needs):
            return "TEMPORAL"
        if len(self.needs) == 1 and self.needs[0].domain in {"diagnosis", "medication", "lab", "vital"}:
            return "STRUCTURED"
        if len(self.needs) == 1 and self.needs[0].domain == "note":
            return "NARRATIVE"
        return "MIXED"

class PlanValidator:
    """Validates the LLM-generated plan deterministically."""
    
    def validate(self, plan: RetrievalPlan, question: str = "") -> RetrievalPlan:
        # Check for empty plan
        if not plan:
            return self._fallback_plan(question)
            
        # Allowed domains
        allowed_domains = {"diagnosis", "medication", "lab", "vital", "encounter", "note", "procedure", "symptom", "all"}
        for need in plan.needs:
            if need.domain not in allowed_domains:
                # If invalid domain found, fallback entirely to avoid arbitrary table access
                return self._fallback_plan(question) if question.strip() else RetrievalPlan(
                    task_type="clinical_question", needs=[DomainNeed(domain="all")],
                    use_structured=True, use_semantic=True, use_lexical=True,
                )
                
        # If task is conversation but retrieval is required, that's fine, but usually it shouldn't be.
        if plan.task_type in {"conversation", "clarification"}:
            plan.retrieval_required = False
            plan.needs = []
        elif plan.task_type == "summary":
            if not plan.needs:
                plan.needs = [DomainNeed(domain="all")]
            # A summary covers the bounded packet; it does not require each
            # selected item to repeat words from the summary request.
            plan.use_lexical = False
            plan.use_semantic = False
        elif plan.task_type == "conflict_check":
            plan.needs = [DomainNeed(domain="all")]
            plan.use_lexical = False
            plan.use_semantic = False
        if plan.comparison_required:
            for need in plan.needs:
                need.temporal.intent = "trend"
            
        return plan
        
    def _fallback_plan(self, question: str = "") -> RetrievalPlan:
        q = question.lower()
        domain: Literal["diagnosis", "medication", "lab", "vital", "encounter", "note", "procedure", "symptom", "all"] = "all"
        intent: Literal["latest", "earliest", "before", "after", "between", "trend", "none"] = "none"
        start_time = None
        end_time = None
        entity = None
        comparison_required = any(marker in q for marker in _COMPARISON_MARKERS)
        relative_months = _relative_months(q)

        if _is_low_information(q) or not _has_clinical_signal(q):
            return RetrievalPlan(task_type="clarification", strict_intent="UNKNOWN", retrieval_required=False)
        
        # Domain parsing
        q_clean = q.replace("bệnh nhân", "").replace("bệnh án", "")
        concept = resolve_concept(q)
        entity = concept.canonical if concept else None
        if "báo cáo" in q or "ghi chú" in q or "note" in q:
            domain = "note"
        elif "thuốc" in q or "medication" in q or (concept and concept.domain == "medication"):
            domain = "medication"
        elif any(marker in q for marker in ("huyết áp", "nhịp tim", "mạch", "cân nặng", "vital")):
            domain = "vital"
        elif any(w in q_clean for w in ["ngày khám", "khám bệnh", "nhập viện", "xuất viện", "đến khám", "lịch khám", "encounter"]):
            domain = "encounter"
        elif any(w in q_clean for w in ["triệu chứng", "biểu hiện", "đau", "sốt", "ho", "symptom", "dấu hiệu"]):
            domain = "symptom"
        elif any(w in q_clean for w in ["bệnh", "chẩn đoán", "tiền sử", "disease", "diagnosis", "condition"]):
            domain = "diagnosis"
            concept_wide = any(marker in q for marker in ("gì", "nào", "what", "which", "tình trạng bệnh"))
            if not concept_wide and q_clean.strip() not in {"bệnh", "diagnosis", "condition"}:
                generic = {
                    "bệnh", "bệnh lý", "bệnh nhân", "chẩn", "chẩn đoán", "của", "đang",
                    "hiện", "hiện tại", "là", "mắc", "người", "nhân", "tình", "tình trạng",
                }
                residue = [token for token in re.findall(r"[\w%/.+-]+", q_clean, flags=re.UNICODE) if len(token) > 1 and token not in generic]
                entity = " ".join(residue) or None
        elif (concept and concept.domain == "lab") or any(marker in q for marker in _LAB_CONCEPT_MARKERS) or "kết quả" in q:
            domain = "lab"
            if entity is None:
                generic_lab_terms = {
                    "bệnh", "bệnh nhân", "bao", "bao nhiêu", "có", "của", "gì",
                    "kết", "kết quả", "là", "nào", "nhân", "patient", "result", "the",
                    "what", "xét", "xét nghiệm", "nghiệm", "các", "chỉ", "số", "thay",
                    "đổi", "ra", "sao", "so", "với", "nửa", "năm", "trước", "tháng",
                    "gần", "đây", "theo", "thời", "gian", "hiện", "tại", "một", "hai",
                    "ba", "bốn", "sáu", "bảy", "tám", "chín", "mười",
                }
                tokens = re.findall(r"[\w%/.+-]+", q, flags=re.UNICODE)
                residue = [token for token in tokens if len(token) > 1 and token not in generic_lab_terms]
                residue = [token for token in residue if token not in {"thay", "đổi", "thời", "gian", "xu", "hướng", "so", "sánh"}]
                entity = " ".join(residue) or None
                
        # Temporal parsing
        if comparison_required or any(marker in q for marker in _TREND_MARKERS + ("biến động", "biến chuyển")):
            intent = "trend"
        elif "gần nhất" in q or "mới nhất" in q:
            intent = "latest"
        elif "trước đó" in q or "lần trước" in q:
            intent = "previous"
            
        from datetime import datetime, timedelta, timezone
        
        # check "N tháng gần đây" / "N tháng qua"
        m = re.search(r"(\d+)\s*tháng\s*(gần đây|qua)", q)
        if m:
            if intent == "none":
                intent = "trend"
            months = int(m.group(1))
            now = datetime.now(timezone.utc)
            start = now - timedelta(days=30*months)
            start_time = start.isoformat()
            end_time = now.isoformat()
            
        # check "trước <date>" or "sau <date>" or "từ <date> đến <date>"
        # Using a very basic regex for dates like YYYY-MM-DD or DD/MM/YYYY for the fallback
        date_pattern = r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})"
        
        m_between = re.search(fr"từ\s+(?:ngày\s+)?{date_pattern}\s+đến\s+(?:ngày\s+)?{date_pattern}", q)
        if m_between:
            intent = "between"
            start_time = m_between.group(1) # We can leave it as string; parse_time will handle it
            end_time = m_between.group(2)
        else:
            m_before = re.search(fr"trước\s+(?:ngày\s+)?{date_pattern}", q)
            if m_before:
                intent = "before"
                start_time = None
                end_time = m_before.group(1)
                
            m_after = re.search(fr"sau\s+(?:ngày\s+)?{date_pattern}", q)
            if m_after:
                intent = "after"
                start_time = m_after.group(1)
                end_time = None
            
        needs = [DomainNeed(
            domain=domain, entity=entity,
            temporal=TemporalIntent(
                intent=intent, start_time=start_time, end_time=end_time,
                relative_months=relative_months,
            ),
        )]
        if entity and entity not in _MEDICATION_ENTITIES and any(
            marker in q for marker in ("thuốc", "medication", "tuân thủ")
        ):
            needs = [
                DomainNeed(
                    domain="lab", entity=entity,
                    temporal=TemporalIntent(
                        intent=intent, start_time=start_time, end_time=end_time,
                        relative_months=relative_months,
                    ),
                ),
                DomainNeed(domain="medication", temporal=TemporalIntent(intent="trend")),
            ]
        return RetrievalPlan(
            task_type="clinical_question",
            needs=needs,
            use_structured=True,
            use_semantic=domain == "all",
            use_lexical=domain == "all",
            retrieval_required=True,
            comparison_required=comparison_required,
        )

class QueryPlanner:
    """
    Query routing prioritizing rule-based classification over LLM.
    """
    def __init__(self):
        self.temporal_keywords = {"latest", "earliest", "previous", "before", "after", "between", "trend", "gần nhất", "trước đây", "sau", "xu hướng"}
        self.structured_keywords = {"hba1c", "glucose", "lab", "xét nghiệm", "chỉ số", "medication", "thuốc", "liều lượng"}
        self.conversational_keywords = _CONVERSATION_MARKERS
        self.validator = PlanValidator()
        
    def plan(self, question: str) -> RetrievalPlan:
        if not question or not question.strip():
            return RetrievalPlan(task_type="clarification", strict_intent="UNKNOWN", retrieval_required=False)
            
        q = question.lower().strip()
        
        # 1. Fast path: conversational
        has_language_content = re.search(r"\w", q, flags=re.UNICODE) is not None
        if not has_language_content:
            return RetrievalPlan(task_type="clarification", strict_intent="UNKNOWN", retrieval_required=False)
        if q in self.conversational_keywords or q.startswith("xin chào"):
            return RetrievalPlan(task_type="conversation", retrieval_required=False)
        if "bạn" in q and any(marker in q for marker in ("giúp", "hỗ trợ", "làm được", "khả năng")):
            return RetrievalPlan(task_type="conversation", retrieval_required=False)
        if _is_low_information(q):
            return RetrievalPlan(task_type="clarification", strict_intent="UNKNOWN", retrieval_required=False)

        if any(marker in q for marker in _CONFLICT_INTENT_MARKERS):
            return self.validator.validate(RetrievalPlan(
                task_type="conflict_check", needs=[DomainNeed(domain="all")],
                use_structured=True, use_semantic=False, use_lexical=False,
            ), question)

        # 2. Fast path: summary
        if any(marker in q for marker in _SUMMARY_INTENT_MARKERS):
            return self.validator.validate(RetrievalPlan(
                task_type="summary",
                needs=[DomainNeed(domain="all")],
                use_structured=True,
                use_semantic=False,
                use_lexical=False,
                retrieval_required=True,
                strict_intent="PATIENT_OVERVIEW"
            ), question)

        deterministic = self.validator._fallback_plan(question)
        
        # 3. Strict Intents (from Task 1)
        is_dated_query = bool(deterministic.needs and deterministic.needs[0].temporal.intent in {"before", "after", "between"})
        
        if any(marker in q for marker in ["tình trạng nào", "không ổn định", "cảnh báo", "bất thường", "có vấn đề gì", "abnormal", "high", "low", "warning", "critical"]):
            deterministic.strict_intent = "WARNING_STATUS"
        elif any(marker in q for marker in ["thông tin của bệnh nhân", "thông tin bệnh nhân", "tình trạng của bệnh nhân", "bệnh nhân hiện tại thế nào"]):
            deterministic.strict_intent = "PATIENT_OVERVIEW"
        elif not is_dated_query and any(marker in q for marker in ["lần khám gần nhất", "buổi khám gần đây nhất", "khám gần nhất", "chỉ số sức khỏe mới nhất", "chỉ số mới nhất", "chỉ số gần nhất", "các chỉ số sức khỏe", "các chỉ số mới nhất", "các chỉ số gần nhất"]):
            deterministic.strict_intent = "LATEST_VISIT"
        elif not is_dated_query and any(marker in q for marker in ["buổi khám trước", "lần khám trước", "khám lần trước"]):
            deterministic.strict_intent = "PREVIOUS_VISIT"
        elif not is_dated_query and any(marker in q for marker in ["buổi khám ngày", "khám ngày", "ngày", "buổi khám"]):
            deterministic.strict_intent = "VISIT"
        elif "bệnh gì" in q or q == "bệnh nhân bị bệnh gì?":
            deterministic.strict_intent = "DISEASE"
        elif "thuốc" in q and "đang dùng" in q:
            deterministic.strict_intent = "MEDICATION"
        elif any(marker in q for marker in ["huyết áp", "nhịp tim", "mạch", "cân nặng"]):
            deterministic.strict_intent = "VITAL_SIGN"
        elif any(marker in q for marker in ["nhiệt độ", "chiều cao", "nhịp thở", "spo2", "oxy"]):
            deterministic.strict_intent = "SPECIFIC_TEST"
            deterministic.extracted_entity = next((m for m in ["nhiệt độ", "chiều cao", "nhịp thở", "spo2", "oxy"] if m in q), None)
        elif any(marker in q for marker in ["hba1c", "glucose"]) or "bao nhiêu" in q:
            if any(marker in q for marker in _COMPARISON_MARKERS + _TREND_MARKERS):
                deterministic.strict_intent = "COMPARISON"
            else:
                deterministic.strict_intent = "LAB_RESULT"

        needs = deterministic.needs
        if deterministic.strict_intent != "NONE":
            deterministic.task_type = "clinical_question"
            return self.validator.validate(deterministic, question)
        if deterministic.task_type != "clinical_question" or (
            needs and needs[0].domain != "diagnosis" and needs[0].domain != "all"
        ):
            return self.validator.validate(deterministic, question)
            
        # 4. LLM Planner for ambiguous cases
        llm_plan = self._llm_plan(question)
        return self.validator.validate(llm_plan, question)
        
    def _llm_plan(self, question: str) -> RetrievalPlan:
        """Call LLM client to parse the plan. For this phase we integrate with llm_client."""
        runtime = get_llm_runtime()
        if not runtime.available:
            return self.validator._fallback_plan(question)

        try:
            parsed = runtime.client.generate_plan(question)
        except Exception:
            parsed = None
        if not parsed:
            return self.validator._fallback_plan(question)
            
        try:
            return RetrievalPlan.model_validate(parsed)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"LLM planner schema validation failed: {e}")
            return self.validator._fallback_plan(question)
